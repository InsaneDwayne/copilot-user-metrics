"""Inbound HTTP adapter for the admin console's Sync page: queue status and run/stop requests."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from copilot_metrics.shared.kernel import Viewer
from copilot_metrics.sync.domain import SyncAction, SyncControlStatus, SyncRequest, SyncTarget
from copilot_metrics.sync.service import SyncControlService


def build_sync_router(*, service: SyncControlService, admin: Callable[..., Any]) -> APIRouter:
    """``admin`` is the FastAPI dependency resolving to an admin's ``Viewer`` (organization readers are refused)."""
    Admin = Annotated[Viewer, Depends(admin)]
    router = APIRouter(prefix="/api/admin/sync", tags=["admin"])

    @router.get("")
    async def sync_control(viewer: Admin) -> SyncControlStatus:
        return await service.status(viewer)

    @router.post("/{target}/{action}", status_code=status.HTTP_202_ACCEPTED)
    async def request(viewer: Admin, target: SyncTarget, action: SyncAction) -> SyncRequest:
        """Accepted, not done: the worker applies the request within seconds."""
        return await service.request(viewer, target, action)

    return router
