"""The synthesized provision op resolves everything from its createVm sibling."""

import os

os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault(
    "SETTINGS_ENC_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
)

from app.routers.deploy import PlanOp  # noqa: E402
from app.tasks import _run_provision_op  # noqa: E402


class _FakeCollection:
    def __init__(self, doc):
        self.doc = doc

    def find_one(self, *args, **kwargs):
        return self.doc


class _FakeDb:
    def __init__(self, registry_doc):
        self.registry_doc = registry_doc

    def __getitem__(self, name):
        assert name == "vm_registry"
        return _FakeCollection(self.registry_doc)


def _plan() -> tuple[PlanOp, list[PlanOp]]:
    create = PlanOp(
        id="create-dc",
        kind="createVm",
        target="dc",
        params={"vmName": "guest-a-lab-dc01", "template": "domainController"},
    )
    provision = PlanOp(
        id="create-dc::provision", kind="provision", target="dc", params={}
    )
    return provision, [create, provision]


def test_agentless_clone_converges_to_done_without_dispatch():
    provision, ops = _plan()
    db = _FakeDb({"vmName": "guest-a-lab-dc01", "ip": "192.168.100.51", "agent": None})
    state = {provision.id: None}
    pushes = []

    ok = _run_provision_op(
        db, provision, ops, "job1", "guest", state, lambda: pushes.append(1)
    )

    assert ok is True
    final = state[provision.id]
    assert final.status == "done"
    assert final.result == {"vmName": "guest-a-lab-dc01", "ip": "192.168.100.51"}
    assert final.steps["agent-ready"].status == "done"
    assert final.steps["boot-settle"].status == "done"
    assert pushes  # progress was published


def test_provision_without_a_createvm_sibling_fails_cleanly():
    provision, _ = _plan()
    state = {provision.id: None}

    ok = _run_provision_op(
        _FakeDb(None), provision, [provision], "job1", "guest", state, lambda: None
    )

    assert ok is False
    assert state[provision.id].status == "error"
    assert "sibling" in state[provision.id].detail
