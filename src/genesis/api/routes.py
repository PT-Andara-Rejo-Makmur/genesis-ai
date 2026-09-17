from fastapi import APIRouter, Request

from genesis import __version__
from genesis.api.models import SystemInfoResponse

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.get("/system/info", response_model=SystemInfoResponse)
async def system_info(_request: Request) -> SystemInfoResponse:
    return SystemInfoResponse(version=__version__)
