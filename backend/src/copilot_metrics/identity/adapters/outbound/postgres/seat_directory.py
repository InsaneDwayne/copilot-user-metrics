from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.identity.ports import SeatDirectory
from copilot_metrics.shared.adapters.outbound.postgres.engine import viewer_scope
from copilot_metrics.shared.adapters.outbound.postgres.tables import seat
from copilot_metrics.shared.kernel import Viewer


class PostgresSeatDirectory(SeatDirectory):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def has_active_seat(self, viewer: Viewer) -> bool:
        query = select(seat.c.user_id).where(seat.c.user_id == viewer.user_id, seat.c.ended_at.is_(None))
        async with viewer_scope(self._engine, viewer) as conn:
            return (await conn.execute(query)).first() is not None
