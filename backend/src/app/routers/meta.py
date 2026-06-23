"""Meta / health routes."""

import configgen
import isokit  # noqa: F401  (declared dep; used by future /iso route)
import vmkit  # noqa: F401
from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    """Liveness check; reports the libraries reachable from the API process."""
    return {
        "status": "ok",
        "libraries": {
            "configgen": list(configgen.PLATFORMS),
            "vmkit": "available",
            "isokit": "available",
        },
    }
