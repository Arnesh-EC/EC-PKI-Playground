"""VM management routes — thin HTTP layer over vmkit.

Every endpoint requires an authenticated ESXi session; the ``X-Session-Token``
header is resolved to a live ``Connection`` by the ``get_session`` dependency
(defined in ``app.core.sessions``).

Note on ``iso_path``: clone/update accept a server-local ``.iso`` filesystem
path. The file must already exist on the host running this API. Building or
uploading ISOs from a client is an isokit concern and is not in scope here.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from vmkit import Connection, clone_workflow, update_workflow
from vmkit.errors import VmNotFoundError
from vmkit.esxi import get_vm_by_name, list_vm_names, power_off_vm, power_on_vm
from vmkit.workflows import get_vm_config, validate_disk_usage

from app.core.sessions import get_session

router = APIRouter(prefix="/vm", tags=["vm"])


# --------------------------------------------------------------------------- #
# Request models                                                              #
# --------------------------------------------------------------------------- #
class CloneRequest(BaseModel):
    name: str
    base: str
    datastore: str
    cpus: int
    mem_mb: int
    mac: str | None = None
    iso_path: str | None = None
    guest_os: str | None = None
    max_usage_pct: float = 80.0
    skip_disk_check: bool = False
    power_on: bool = False


class UpdateRequest(BaseModel):
    datastore: str
    cpus: int | None = None
    mem_mb: int | None = None
    mac: str | None = None
    iso_path: str | None = None
    remove_iso: bool = False
    power_on: bool = False


class DiskCheckRequest(BaseModel):
    datastore: str
    base: str
    max_usage_pct: float = 80.0


# --------------------------------------------------------------------------- #
# Endpoints (static routes before /{name} to avoid path collisions)           #
# --------------------------------------------------------------------------- #
@router.post("/clone")
def clone(req: CloneRequest, conn: Connection = Depends(get_session)) -> dict:
    """Clone a base VM: server-side disk copy, render+upload VMX, register."""
    result = clone_workflow(conn, **req.model_dump())
    return asdict(result)


@router.post("/disk-check")
def disk_check(req: DiskCheckRequest, conn: Connection = Depends(get_session)) -> dict:
    """Report datastore space usage; 409 if cloning the base would exceed the limit."""
    usage = validate_disk_usage(conn.content, req.datastore, req.base, req.max_usage_pct)
    return asdict(usage)


@router.get("")
def list_vms(conn: Connection = Depends(get_session)) -> dict:
    """List all VM names in inventory."""
    names = sorted(list_vm_names(conn.content))
    return {"vms": names, "count": len(names)}


@router.get("/{name}")
def get_vm(name: str, conn: Connection = Depends(get_session)) -> dict:
    """Return the current CPU/RAM/MAC and power state of a registered VM."""
    vm = get_vm_by_name(conn.content, name)
    if vm is None:
        raise VmNotFoundError(f"VM '{name}' not found.")
    config = get_vm_config(vm)
    return {"name": name, "power_state": str(vm.runtime.powerState), **config}


@router.patch("/{name}")
def update_vm(
    name: str, req: UpdateRequest, conn: Connection = Depends(get_session)
) -> dict:
    """Reconfigure an existing VM's CPU/RAM/MAC/ISO; unspecified values are preserved."""
    result = update_workflow(conn, name=name, **req.model_dump())
    return asdict(result)


@router.post("/{name}/power-on")
def power_on(name: str, conn: Connection = Depends(get_session)) -> dict:
    """Power on the named VM."""
    power_on_vm(conn.content, name)
    return {"status": "powered_on", "name": name}


@router.post("/{name}/power-off")
def power_off(name: str, conn: Connection = Depends(get_session)) -> dict:
    """Power off (hard) the named VM."""
    power_off_vm(conn.content, name)
    return {"status": "powered_off", "name": name}
