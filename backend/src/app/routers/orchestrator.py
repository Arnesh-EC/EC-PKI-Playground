"""Orchestrator phone-home routes.

The Rust orchestrator agent (``pki-orchestrator``, a separate repo) connects
outbound to ``ws /api/orchestrator/connect`` once running, authenticating
with a vm_id/token pair minted by ``POST /orchestrator/register``. This
stands in for what a real deployment will eventually bake into the boot ISO
automatically — see ``pki-orchestrator/README.md``'s "Future integration
points": ``isokit`` can't embed a compiled binary yet, and ``vmkit`` has no
guest-correlation mechanism.

The connect route's own coroutine is both the agent's live connection and
the relay of its progress frames onto the existing job-progress transport
(``app.core.jobs.transport``) — reusing the single-linear-job message family
(``ProgressMsg``/``DoneMsg``/``ErrorMsg``) and the existing
``/ws/jobs/{job_id}`` WebSocket, so no new wire shape is needed on the
frontend side.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core import agents
from app.core.authz import Capability, require_capability
from app.core.jobs import transport
from app.core.jobs.models import DoneMsg, ErrorMsg, JobStatus, ProgressMsg

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class RegisterResponse(BaseModel):
    vm_id: str
    token: str


@router.post(
    "/register",
    dependencies=[Depends(require_capability(Capability.VM_CLONE))],
)
def register() -> RegisterResponse:
    """Mint a vm_id/token pair for a not-yet-connected orchestrator agent.

    A human copies both values into that agent's ``orchestrator.toml`` before
    running it — see the module docstring for why this is manual today.
    Gated on ``VM_CLONE`` for the same reason ``DEPLOY`` is guest-eligible:
    a guest registering an agent for a VM it could already clone doesn't
    grant anything it couldn't already do.
    """
    vm_id, token = agents.register_agent()
    return RegisterResponse(vm_id=vm_id, token=token)


@router.websocket("/connect")
async def connect(websocket: WebSocket, vm_id: str | None = None, token: str | None = None) -> None:
    """Accept an orchestrator agent's phone-home connection and relay its progress.

    Auth mirrors ``routers.ws``'s convention: validated before ``accept()``,
    closed with 4401 on failure (here: unknown/already-consumed vm_id, or a
    token mismatch) rather than a normal HTTP error, since this is a
    WebSocket upgrade.
    """
    if not vm_id or not token or not agents.authenticate_pending(vm_id, token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    agents.connect_agent(vm_id, websocket)
    try:
        while True:
            frame = await websocket.receive_json()
            job_id = frame.get("job_id")
            state = frame.get("state")
            if job_id and state:
                _relay_progress(job_id, state)
    except WebSocketDisconnect:
        pass
    finally:
        agents.disconnect_agent(vm_id)


def _relay_progress(job_id: str, state: dict) -> None:
    """Translate one orchestrator `OpRunState` frame onto the existing job transport.

    `pending`/`cancelled` are never emitted by the orchestrator's own
    `report.rs` helpers (only `running`/`done`/`error` are) — anything else
    is ignored rather than guessed at.
    """
    status = state.get("status")
    if status == "running":
        transport.publish(
            job_id,
            ProgressMsg(percent=state.get("percent") or 0.0, phase=state.get("phase") or "", key=job_id),
            status=JobStatus.running,
        )
    elif status == "done":
        transport.publish(
            job_id, DoneMsg(result=state.get("result") or {}), status=JobStatus.done, terminal=True
        )
    elif status == "error":
        transport.publish(
            job_id,
            ErrorMsg(status=500, detail=state.get("detail") or "orchestrator command failed"),
            status=JobStatus.error,
            terminal=True,
        )
