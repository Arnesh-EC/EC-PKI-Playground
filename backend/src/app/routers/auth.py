"""Auth routes — ESXi session lifecycle and deploy-mode discovery.

Session bootstrap differs by deploy mode (set via AUTH_MODE env var):

  login (internal/operator)
    POST /auth/connect   — client provides ESXi credentials; returns a token.
    POST /auth/disconnect — invalidates the token.
    GET  /auth/mode      — returns {"mode":"login","role":"operator","capabilities":[…]}
    POST /auth/guest     — 403 (not available in login mode)

  guest (public playground)
    POST /auth/guest     — opens a session from hardcoded .env ESXi creds; returns a token.
    GET  /auth/mode      — returns {"mode":"guest","role":"guest","capabilities":[…]}
    POST /auth/connect   — 403 (guests must not supply arbitrary host/creds)
    POST /auth/disconnect — available (though the frontend hides the logout button)

Credentials for the login mode travel only in the /auth/connect request body and
are not stored anywhere on the server — the live Connection object is kept in the
in-process session store (core/sessions.py). Guest-mode credentials live in .env
and are never returned to the client.
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from vmkit import open_connection

from app.core.authz import Capability, capabilities_for, current_role
from app.core.sessions import create_session, drop_session
from app.core.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


# --------------------------------------------------------------------------- #
# Mode discovery (unauthenticated — called by the frontend on every load)     #
# --------------------------------------------------------------------------- #


@router.get("/mode")
def get_mode() -> dict:
    """Return the deploy's auth mode, implied role, and capability allowlist.

    The frontend uses ``mode`` to decide login-form vs auto-connect, and
    ``capabilities`` to conditionally render operator-only UI.
    """
    role = current_role()
    return {
        "mode": settings.auth_mode,
        "role": role.value,
        "capabilities": capabilities_for(role),
    }


# --------------------------------------------------------------------------- #
# Login-mode endpoints                                                         #
# --------------------------------------------------------------------------- #


class ConnectRequest(BaseModel):
    host: str
    user: str
    password: str
    port: int = 443


@router.post("/connect")
def connect(req: ConnectRequest) -> dict:
    """Open an ESXi/vCenter session (login mode only) and return a token.

    Raises 403 in guest mode — a public visitor must not be able to point the
    API at an arbitrary host with arbitrary credentials.
    Raises 401 on bad credentials (AuthenticationError) or 502 if the host is
    unreachable (ConnectionFailedError) — both mapped by the app-level handlers.
    """
    if settings.auth_mode == "guest":
        raise HTTPException(
            status_code=403,
            detail="Manual login is not available in guest mode.",
        )
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


# --------------------------------------------------------------------------- #
# Guest-mode endpoint                                                          #
# --------------------------------------------------------------------------- #


@router.post("/guest")
def guest_connect() -> dict:
    """Open a session from the hardcoded playground ESXi creds (guest mode only).

    The frontend calls this automatically on load — no credentials are sent by
    the client. Raises 403 in login mode.
    """
    if settings.auth_mode == "login":
        raise HTTPException(
            status_code=403,
            detail="Guest auto-connect is not available in login mode.",
        )
    # settings validator guarantees these are non-None in guest mode.
    conn = open_connection(
        settings.esxi_host,  # type: ignore[arg-type]
        settings.esxi_user,  # type: ignore[arg-type]
        settings.esxi_password,  # type: ignore[arg-type]
        settings.esxi_port,
    )
    token = create_session(conn)
    return {
        "token": token,
        "host": conn.host,
        "api_version": conn.content.about.fullName,
    }
