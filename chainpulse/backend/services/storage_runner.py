"""Standalone storage consumer runner.

    python -m chainpulse.backend.services.storage_runner
"""
from __future__ import annotations

import asyncio
import logging
import signal

from chainpulse.backend.services.storage_pipeline import run_consumer

log = logging.getLogger("chainpulse.storage.runner")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = asyncio.Event()

    def _sig(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except NotImplementedError:
            pass

    task = asyncio.create_task(run_consumer())
    await stop.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
