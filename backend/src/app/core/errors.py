"""App-level exception handlers: vmkit typed errors → HTTP status codes.

Register by calling ``register_exception_handlers(app)`` in the app factory.
Each handler returns a ``{"detail": ...}`` JSON body matching FastAPI/Pydantic's
own error format so callers need only one error-parsing branch.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vmkit.errors import (
    AuthenticationError,
    ConnectionFailedError,
    InsufficientSpaceError,
    ValidationError,
    VmExistsError,
    VmkitError,
    VmNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach vmkit-error→HTTP handlers to *app*.

    Handlers are registered most-specific first; FastAPI dispatches via
    isinstance so the base-class catch-all (VmkitError→500) fires only when
    no more specific handler matches.
    """

    @app.exception_handler(ValidationError)
    async def _validation_error(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def _auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(ConnectionFailedError)
    async def _conn_error(request: Request, exc: ConnectionFailedError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(VmExistsError)
    async def _vm_exists(request: Request, exc: VmExistsError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(VmNotFoundError)
    async def _vm_not_found(request: Request, exc: VmNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InsufficientSpaceError)
    async def _insufficient_space(
        request: Request, exc: InsufficientSpaceError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(VmkitError)
    async def _vmkit_error(request: Request, exc: VmkitError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
