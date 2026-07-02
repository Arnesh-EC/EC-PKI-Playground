"""In-process registry correlating an orchestrator agent to a VM.

Two stages, mirroring ``sessions.py``'s own tradeoffs (no TTL, no
persistence, lost on process restart — restart cascades to the agent's
reconnect-with-backoff loop finding no pending/connected entry, same as a
lost session cascades to a 401 on the frontend):

* ``_pending``: a vm_id/token pair minted by ``register_agent``, before the
  agent has actually connected. Stands in for what a real deployment will
  eventually bake into the boot ISO automatically, once ``isokit``/
  ``configgen`` grow the binary-embedding/plugin points they're missing
  today (see ``pki-orchestrator/README.md``'s "Future integration points").
* ``_connected``: promoted from ``_pending`` once the agent's WebSocket
  authenticates against it (``routers.orchestrator.connect``). Holds the
  live ``WebSocket`` plus a send lock, since a dispatched command
  (``POST /orchestrator/{vm_id}/command``, a different request's coroutine
  than the one that accepted the connection) writes to that same socket.
"""

import asyncio
import threading
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

_pending: dict[str, str] = {}  # vm_id -> token
_connected: dict[str, "AgentConnection"] = {}  # vm_id -> live connection
_lock = threading.Lock()


@dataclass
class AgentConnection:
    websocket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, payload: dict) -> None:
        async with self.send_lock:
            await self.websocket.send_json(payload)


def register_agent() -> tuple[str, str]:
    """Mint a fresh vm_id/token pair and store it pending a connection."""
    vm_id = uuid.uuid4().hex[:12]
    token = uuid.uuid4().hex
    with _lock:
        _pending[vm_id] = token
    return vm_id, token


def authenticate_pending(vm_id: str, token: str) -> bool:
    """True and consumes the entry if vm_id/token match a pending registration."""
    with _lock:
        expected = _pending.get(vm_id)
        if expected is None or expected != token:
            return False
        del _pending[vm_id]
        return True


def connect_agent(vm_id: str, websocket: WebSocket) -> AgentConnection:
    conn = AgentConnection(websocket=websocket)
    with _lock:
        _connected[vm_id] = conn
    return conn


def disconnect_agent(vm_id: str) -> None:
    with _lock:
        _connected.pop(vm_id, None)


def resolve_agent(vm_id: str) -> AgentConnection | None:
    with _lock:
        return _connected.get(vm_id)


def connected_vm_ids() -> list[str]:
    with _lock:
        return sorted(_connected.keys())
