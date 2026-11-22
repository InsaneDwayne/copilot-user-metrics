"""Inbound adapter: the worker applies run/stop requests from the admin console.

The API wakes it with ``NOTIFY`` on ``channel`` (the outbound adapter that writes the
requests owns its name; the composition root passes it in). The worker also looks every
``poll_seconds`` in case a notification was missed (say, while it reconnected).
"""

import asyncio
import logging

import psycopg
from psycopg import sql

from copilot_metrics.sync.ports import RequestInbox
from copilot_metrics.sync.service import SyncRequestHandler

log = logging.getLogger(__name__)


async def apply_requests(
    conninfo: str, channel: str, inbox: RequestInbox, handler: SyncRequestHandler, poll_seconds: float = 30
) -> None:
    """Runs until cancelled; connection errors are logged and retried."""
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
                await conn.execute(sql.SQL("LISTEN {}").format(sql.Identifier(channel)))
                while True:
                    if handled := await inbox.handle_pending(handler.handle):
                        log.info("applied %d sync request(s) from the admin console", handled)
                    async for _ in conn.notifies(timeout=poll_seconds, stop_after=1):
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("sync requests: listener failed, retrying in %ss", poll_seconds)
            await asyncio.sleep(poll_seconds)
