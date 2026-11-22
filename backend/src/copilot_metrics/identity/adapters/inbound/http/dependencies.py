"""FastAPI dependencies that turn the session cookie into a ``Viewer`` or refuse the request.

They raise identity domain errors; the central error handler maps them to 401/403.
"""

from typing import Annotated

from fastapi import Depends, Request
from pydantic import ValidationError

from copilot_metrics.identity.domain import (
    AdminsOnly,
    NoSeat,
    NotOrgMember,
    NotSignedIn,
    OrgReadersOnly,
    SessionExpired,
    SessionInvalid,
    SessionUser,
)
from copilot_metrics.identity.ports import SeatDirectory
from copilot_metrics.settings import SessionSettings
from copilot_metrics.shared.adapters.inbound.http.middleware import USER_KEY
from copilot_metrics.shared.kernel import Clock, Role, Viewer


class Guards:
    """FastAPI dependencies that turn the session cookie into a ``Viewer``.

    Usage routes never take a login from the request: the subject is always the
    session's own user, unless an admin route resolves it explicitly.
    """

    def __init__(self, settings: SessionSettings, seats: SeatDirectory, clock: Clock) -> None:
        def current_user(request: Request) -> SessionUser:
            raw = request.session.get(USER_KEY)
            if raw is None:
                raise NotSignedIn
            try:
                user = SessionUser.model_validate(raw)
            except ValidationError:
                request.session.clear()
                raise SessionInvalid from None
            if user.is_expired(clock.now(), settings.max_age):
                request.session.clear()
                raise SessionExpired
            return user

        async def has_seat(viewer: Viewer) -> bool:
            return viewer.role is not Role.OUTSIDER and await seats.has_active_seat(viewer)

        async def seat_holder(user: Annotated[SessionUser, Depends(current_user)]) -> Viewer:
            viewer = user.viewer()
            if viewer.can_read_org:  # admins and organization readers may lack a seat but still see their (empty) usage
                return viewer
            if not await has_seat(viewer):
                raise NoSeat
            return viewer

        def org_member(user: Annotated[SessionUser, Depends(current_user)]) -> Viewer:
            if user.role is Role.OUTSIDER:
                raise NotOrgMember
            return user.viewer()

        def org_reader(user: Annotated[SessionUser, Depends(current_user)]) -> Viewer:
            """Every member's usage: admins and organization readers."""
            viewer = user.viewer()
            if not viewer.can_read_org:
                raise OrgReadersOnly
            return viewer

        def admin(user: Annotated[SessionUser, Depends(current_user)]) -> Viewer:
            """Sync control: admins only."""
            viewer = user.viewer()
            if not viewer.is_admin:
                raise AdminsOnly
            return viewer

        self.current_user = current_user
        self.has_seat = has_seat
        self.seat_holder = seat_holder
        self.org_member = org_member
        self.org_reader = org_reader
        self.admin = admin
