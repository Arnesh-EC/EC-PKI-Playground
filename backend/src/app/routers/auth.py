"""Auth routes — ESXi session lifecycle.

``POST /auth/connect`` opens an ESXi/vCenter connection and returns an opaque
token. Clients pass that token back in the ``X-Session-Token`` header on every
subsequent call. ``POST /auth/disconnect`` invalidates it.

Credentials travel only in the ``/auth/connect`` request body and are not stored
anywhere on the server — the live ``Connection`` object (which holds them for
datastore HTTP transfers) is kept in the in-process session store.
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from vmkit import open_connection

from app.core.sessions import create_session, drop_session

router = APIRouter(prefix="/auth", tags=["auth"])


class ConnectRequest(BaseModel):
    host: str
    user: str
    password: str
    port: int = 443


@router.post("/connect")
def connect(req: ConnectRequest) -> dict:
    """Open an ESXi/vCenter session and return a token for subsequent calls.

    Raises 401 on bad credentials (AuthenticationError) or 502 if the host is
    unreachable (ConnectionFailedError) — mapped by the app-level error handlers.
    """
    conn = open_connection(req.host, req.user, req.password, req.port)
    token = create_session(conn)
    return {
        "token": token,
        "host": conn.host,
        "api_version": conn.content.about.fullName,
    }


@router.post("/disconnect")
def disconnect(x_session_token: str = Header(...)) -> dict:
    """Invalidate the current session token."""
    if not drop_session(x_session_token):
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")
    return {"status": "disconnected"}
