"""Celery tasks. Runs in the worker process — never inside the FastAPI app.

The clone task owns the blocking vmkit call and publishes progress over the Valkey
transport (``app.core.jobs.transport``). It reuses ``CloneProgressReducer`` and
``_clone_total_ops`` from the clone route unchanged, and ``map_vmkit_error`` for the
same error → status mapping the synchronous routes use.

The plan runner (``run_plan_task``) walks a validated deploy-plan DAG the same
way. Since Phase G every ``createVm`` op is a real vmkit clone booted from a
per-VM firstboot ISO (``core.firstboot``) that bakes in an address claimed
from the guest IP pool (``core.ippool``); the other op kinds are timed stubs.
Like the clone task, it opens its own ESXi connection against the shared
org-wide target from the Mongo settings document (``core.esxi.load_target_sync``
— the async client is API-process-bound), so the worker needs Mongo +
``SETTINGS_ENC_KEY``, not ``ESXI_*`` env vars. Its Mongo writes (IP
allocation, vm_registry) go through one short-lived sync client per task
(``core.db.sync.worker_db``).
"""

import time
import uuid
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from pyVim.connect import Disconnect
from vmkit import clone_workflow, destroy_workflow, open_connection
from vmkit.errors import VmExistsError, VmkitError, VmNotFoundError
from vmkit.esxi import get_vm_by_name

from app.celery_app import celery_app
from app.core.db.models import now_ms
from app.core.db.sync import worker_db
from app.core.errors import map_vmkit_error
from app.core.esxi import load_target_sync
from app.core.firstboot import build_firstboot_iso
from app.core.ippool import (
    IpPoolExhaustedError,
    allocate_ip_sync,
    load_guest_network_sync,
    release_ip_sync,
)
from app.core.jobs import transport
from app.core.jobs.models import (
    DoneMsg,
    ErrorMsg,
    JobStatus,
    OpRunState,
    PlanStateMsg,
    ProgressMsg,
    RunningMsg,
)


def _open_worker_connection():
    """Shared-target connection for one task; raises if no target is configured
    (the API routes pre-check this, so hitting it here means the target was
    unset between enqueue and execution)."""
    target = load_target_sync()
    if target is None:
        raise RuntimeError("No shared ESXi target configured (settings document).")
    return open_connection(target.host, target.user, target.password, target.port)

if TYPE_CHECKING:
    from vmkit import Connection

    from app.routers.deploy import PlanOp

#: Server-side mirror of the frontend's STANDALONE_CLONE (constants/templates.ts /
#: the pre-staging topology.ts) — the backend does not accept arbitrary hardware
#: params from the client, only the per-VM name.
PLAN_CLONE_DEFAULTS = {
    "base": "ws-2025-base",
    "datastore": "datastore1",
    "cpus": 2,
    "mem_mb": 4096,
}

#: Three named phases per simulated op kind, ticked at a fixed cadence.
#: ``createVm`` is deliberately absent — it is always a real clone (Phase G).
_SIMULATED_PHASES: dict[str, tuple[str, str, str]] = {
    "domainJoin": ("Joining domain", "Rebooting", "Verifying membership"),
    "domainLeave": ("Leaving domain", "Rebooting", "Verifying removal"),
    "caConnect": ("Generating CSR", "Signing certificate", "Installing CA certificate"),
    "webServerCert": ("Requesting certificate", "Binding to IIS", "Publishing CDP/AIA"),
}
_SIMULATED_PERCENTS = (33.0, 66.0, 100.0)
_SIMULATED_STEP_SECONDS = 0.6


@celery_app.task(name="clone_vm")
def clone_vm_task(job_id: str, params: dict) -> None:
    # Imported lazily to avoid a hard import-time dependency between the worker
    # entrypoint and the FastAPI router module.
    from app.routers.vm import CloneProgressReducer, CloneRequest, _clone_total_ops

    transport.publish(job_id, RunningMsg(), status=JobStatus.running)

    try:
        req = CloneRequest(**params)
        conn = _open_worker_connection()
        reducer = CloneProgressReducer(transport.make_publisher(job_id), _clone_total_ops(req))
        result = clone_workflow(conn, progress=reducer, **params)
        transport.publish(
            job_id, DoneMsg(result=asdict(result)), status=JobStatus.done, terminal=True
        )
    except VmkitError as exc:
        status, detail = map_vmkit_error(exc)
        transport.publish(
            job_id, ErrorMsg(status=status, detail=detail), status=JobStatus.error, terminal=True
        )
    except Exception as exc:  # noqa: BLE001 — surface anything as a terminal error
        transport.publish(
            job_id, ErrorMsg(status=500, detail=str(exc)), status=JobStatus.error, terminal=True
        )


@celery_app.task(name="destroy_vm")
def destroy_vm_task(job_id: str, name: str) -> None:
    """Tear down a VM: power off + destroy, reclaim its guest IP, mark the
    registry entry deleted.

    A VM already absent from inventory (``VmNotFoundError``) still converges
    to success — the clone may have half-failed leaving only registry/IP
    state, and that must be cleanable through the same teardown call. Any
    other vmkit failure leaves the allocation in place (the VM still exists
    and may be using the address).
    """
    from app.routers.vm import CloneProgressReducer

    transport.publish(job_id, RunningMsg(), status=JobStatus.running)

    try:
        conn = _open_worker_connection()
        try:
            already_absent = False
            try:
                # Two ops: power off + destroy (the reducer only needs a total).
                reducer = CloneProgressReducer(transport.make_publisher(job_id), 2)
                destroy_workflow(conn, name=name, progress=reducer)
            except VmNotFoundError:
                already_absent = True
        finally:
            Disconnect(conn.si)

        with worker_db() as db:
            release_ip_sync(db, name)
            db["vm_registry"].update_one(
                {"vmName": name},
                {
                    "$set": {
                        "status": "deleted",
                        "powerState": None,
                        "ip": None,
                        "updatedAt": now_ms(),
                    }
                },
            )

        transport.publish(
            job_id,
            DoneMsg(result={"name": name, "alreadyAbsent": already_absent}),
            status=JobStatus.done,
            terminal=True,
        )
    except VmkitError as exc:
        status, detail = map_vmkit_error(exc)
        transport.publish(
            job_id, ErrorMsg(status=status, detail=detail), status=JobStatus.error, terminal=True
        )
    except Exception as exc:  # noqa: BLE001 — surface anything as a terminal error
        transport.publish(
            job_id, ErrorMsg(status=500, detail=str(exc)), status=JobStatus.error, terminal=True
        )


def _op_progress_publisher(state: dict[str, OpRunState], op_id: str, push):
    """``Publish``-shaped callable that folds ``ProgressMsg`` samples from
    ``CloneProgressReducer`` into this op's slot in the plan state, then pushes
    the whole snapshot."""

    def _publish(msg) -> None:
        if isinstance(msg, ProgressMsg):
            state[op_id] = OpRunState(status="running", percent=msg.percent, phase=msg.phase)
            push()

    return _publish


def _registry_upsert_sync(db, vm_name: str, **fields) -> None:
    """Worker-side mirror of ``routers/vm_registry.upsert_entry`` (same
    ``vmName`` key and ``$setOnInsert`` identity pinning, sync client)."""
    fields["updatedAt"] = now_ms()
    db["vm_registry"].update_one(
        {"vmName": vm_name},
        {
            "$set": fields,
            "$setOnInsert": {
                "_id": uuid.uuid4().hex,
                "createdAt": now_ms(),
                "schemaVersion": 1,
            },
        },
        upsert=True,
    )


def _run_clone_op(
    conn: "Connection", db, op: "PlanOp", job_id: str, state: dict[str, OpRunState], push
) -> bool:
    """Execute a ``createVm`` op for real: claim a guest IP, build the per-VM
    firstboot ISO, clone (ISO attached, powered on), record the registry entry.
    Returns False on failure — the claimed IP is released so a failed op never
    strands an address."""
    from app.routers.vm import CloneProgressReducer, CloneRequest, _clone_total_ops

    vm_name = op.params["vmName"]
    state[op.id] = OpRunState(status="running", percent=0.0, phase="Starting")
    push()

    net = load_guest_network_sync(db)
    if net is None:
        # The route rejects plans without a configured range; hitting this
        # means it was cleared between enqueue and execution.
        state[op.id] = OpRunState(status="error", detail="Guest IP range is not configured.")
        push()
        return False
    try:
        ip = allocate_ip_sync(db, vm_name, job_id)
    except IpPoolExhaustedError as exc:
        state[op.id] = OpRunState(status="error", detail=str(exc))
        push()
        return False

    _registry_upsert_sync(
        db, vm_name, appName=op.target, status="cloning", jobId=job_id, ip=ip
    )
    try:
        with TemporaryDirectory() as tmp:
            iso = build_firstboot_iso(
                template=op.params["template"],
                vm_name=vm_name,
                ip=ip,
                net=net,
                dest_dir=Path(tmp),
            )
            req = CloneRequest(
                name=vm_name,
                iso_path=str(iso),
                power_on=True,
                **PLAN_CLONE_DEFAULTS,
            )
            reducer = CloneProgressReducer(
                _op_progress_publisher(state, op.id, push), _clone_total_ops(req)
            )
            result = clone_workflow(conn, progress=reducer, **req.model_dump())

        vm = get_vm_by_name(conn.content, vm_name)
        _registry_upsert_sync(
            db,
            vm_name,
            status="ready",
            moid=vm._moId if vm is not None else None,
            powerState="poweredOn",
        )
        state[op.id] = OpRunState(
            status="done",
            percent=100.0,
            phase="Done",
            # ip/vmName ride the op result so the frontend can label the node
            # and key teardown off the real inventory name.
            result={**asdict(result), "ip": ip, "vmName": vm_name},
        )
        push()
        return True
    except VmExistsError as exc:
        # A VM by this name is already in inventory (redelivered task, or a
        # re-deploy over a survivor) — it may well be running with this very
        # address baked into its ISO, so the allocation is deliberately KEPT;
        # tearing the VM down is what releases it.
        status, detail = map_vmkit_error(exc)
        state[op.id] = OpRunState(status="error", detail=f"{status}: {detail}")
        push()
        return False
    except VmkitError as exc:
        status, detail = map_vmkit_error(exc)
        release_ip_sync(db, vm_name)
        _registry_upsert_sync(db, vm_name, status="error", ip=None)
        state[op.id] = OpRunState(status="error", detail=f"{status}: {detail}")
        push()
        return False
    except Exception as exc:  # noqa: BLE001 — surface as an op-level failure, not a plan crash
        release_ip_sync(db, vm_name)
        _registry_upsert_sync(db, vm_name, status="error", ip=None)
        state[op.id] = OpRunState(status="error", detail=str(exc))
        push()
        return False


def _simulate_op(op: "PlanOp", state: dict[str, OpRunState], push) -> bool:
    """Advance a stubbed op through its 3 named phases. Always succeeds in v1."""
    phases = _SIMULATED_PHASES[op.kind.value]
    for phase, percent in zip(phases, _SIMULATED_PERCENTS):
        time.sleep(_SIMULATED_STEP_SECONDS)
        state[op.id] = OpRunState(status="running", percent=percent, phase=phase)
        push()
    state[op.id] = OpRunState(
        status="done", percent=100.0, phase=phases[-1], result={"simulated": True}
    )
    push()
    return True


@celery_app.task(name="run_plan")
def run_plan_task(job_id: str, plan: dict) -> None:
    """Walk a validated deploy-plan DAG, running each op in dependency order.

    Sequential ready-set loop (Kahn-style): repeatedly pick the first remaining
    op whose dependencies have all finished. A dependency that ended in error or
    was itself cancelled poisons its dependents — they're marked ``cancelled``
    and skipped rather than executed, so one failed clone doesn't take down
    independent branches of the plan. The whole body is wrapped in one
    try/except mirroring ``clone_vm_task``: only plan-level infrastructure
    failures (bad payload) become a terminal ``ErrorMsg``; per-op failures —
    including a failed ``open_connection`` attempt, caught around just that
    call — are folded into the op's state and the plan always finishes with a
    ``DoneMsg``. The ESXi connection (opened lazily, at most once) is closed
    in a ``finally`` regardless of outcome.
    """
    from app.routers.deploy import DeployRequest, PlanOpKind

    try:
        ops = DeployRequest(**plan).ops
        state: dict[str, OpRunState] = {op.id: OpRunState(status="pending") for op in ops}

        def push() -> None:
            transport.publish(job_id, PlanStateMsg(ops=dict(state)), status=JobStatus.running)

        transport.publish(job_id, RunningMsg(), status=JobStatus.running)
        push()

        remaining = list(ops)
        finished: set[str] = set()
        blocked: set[str] = set()
        conn: "Connection | None" = None
        # One sync Mongo client for the whole plan, opened only when there is
        # a createVm to run (IP allocation + registry writes live there).
        needs_db = any(op.kind is PlanOpKind.create_vm for op in ops)
        db_ctx = worker_db() if needs_db else nullcontext(None)

        try:
            with db_ctx as db:
                while remaining:
                    for idx, op in enumerate(remaining):
                        if all(dep in finished for dep in op.depends_on):
                            del remaining[idx]
                            break
                    else:
                        # Unreachable given a validated (acyclic, all-deps-present) plan —
                        # guard against an infinite loop rather than hang the worker.
                        for op in remaining:
                            state[op.id] = OpRunState(
                                status="cancelled", detail="Unresolvable dependency ordering."
                            )
                            finished.add(op.id)
                            blocked.add(op.id)
                            push()
                        break

                    if any(dep in blocked for dep in op.depends_on):
                        state[op.id] = OpRunState(
                            status="cancelled", detail="Skipped: a dependency failed or was cancelled."
                        )
                        finished.add(op.id)
                        blocked.add(op.id)
                        push()
                        continue

                    if op.kind is PlanOpKind.create_vm:
                        if conn is None:
                            try:
                                conn = _open_worker_connection()
                            except Exception as exc:  # noqa: BLE001 — a connection failure blocks this op only, not the whole plan
                                state[op.id] = OpRunState(status="error", detail=str(exc))
                                push()
                                finished.add(op.id)
                                blocked.add(op.id)
                                continue
                        ok = _run_clone_op(conn, db, op, job_id, state, push)
                    else:
                        ok = _simulate_op(op, state, push)

                    finished.add(op.id)
                    if not ok:
                        blocked.add(op.id)
        finally:
            if conn is not None:
                Disconnect(conn.si)

        transport.publish(
            job_id,
            DoneMsg(result={"ops": {op_id: s.model_dump() for op_id, s in state.items()}}),
            status=JobStatus.done,
            terminal=True,
        )
    except VmkitError as exc:
        status, detail = map_vmkit_error(exc)
        transport.publish(
            job_id, ErrorMsg(status=status, detail=detail), status=JobStatus.error, terminal=True
        )
    except Exception as exc:  # noqa: BLE001 — surface anything as a terminal error
        transport.publish(
            job_id, ErrorMsg(status=500, detail=str(exc)), status=JobStatus.error, terminal=True
        )
