"""Config-script generation routes — thin HTTP layer over configgen.

The route handlers do exactly what the gen-* CLIs do: build the request into
configgen's pure API and return the rendered script as text/plain. configgen's
ValidationError maps to HTTP 422.
"""

import configgen
from configgen import NetworkConfig, ValidationError
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

router = APIRouter(prefix="/generate", tags=["config-scripts"])


class HostnameRequest(BaseModel):
    platform: str  # "linux" | "windows"
    hostname: str


class NetworkRequest(BaseModel):
    platform: str
    dhcp: bool = False
    ip: str | None = None
    prefix: int | None = None
    gateway: str | None = None
    dns1: str | None = None
    dns2: str | None = None
    dns_suffix: str | None = None


@router.post("/hostname", response_class=PlainTextResponse)
def generate_hostname(req: HostnameRequest) -> str:
    try:
        return configgen.render_hostname(req.platform, req.hostname)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/network", response_class=PlainTextResponse)
def generate_network(req: NetworkRequest) -> str:
    try:
        cfg = NetworkConfig(
            mode="dhcp" if req.dhcp else "static",
            ip=req.ip,
            prefix=req.prefix,
            gateway=req.gateway,
            dns1=req.dns1,
            dns2=req.dns2,
            dns_suffix=req.dns_suffix,
        )
        return configgen.render_network(req.platform, cfg)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
