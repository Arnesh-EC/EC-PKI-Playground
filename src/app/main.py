"""FastAPI application entry point.

Imports all three libraries at startup (proving they're consumable as git deps)
and mounts the config-script generation routes. clone/update (vmkit) and ISO
packing (isokit) endpoints are TODO — they need ESXi credentials / file uploads.
"""

import configgen
import isokit  # noqa: F401  (declared dep; used by future /iso route)
import vmkit  # noqa: F401  (declared dep; used by future /vm/* routes)
from fastapi import FastAPI

from app.routers import config

app = FastAPI(
    title="vm-deploy-api",
    version="0.1.0",
    description="HTTP API over vmkit / configgen / isokit for VM deployment.",
)

app.include_router(config.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness check; also reports the libraries reachable from the API process."""
    return {
        "status": "ok",
        "libraries": {
            "configgen": list(configgen.PLATFORMS),
            "vmkit": "available",
            "isokit": "available",
        },
    }
