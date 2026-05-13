"""Standalone ingest runner. Run as a separate process or worker container.

    python -m chainpulse.backend.ingest.runner
"""
from __future__ import annotations

import asyncio
import logging
import signal

from chainpulse.backend.ingest.scheduler import build_scheduler

log = logging.getLogger("chainpulse.ingest.runner")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sched = build_scheduler()
    sched.start()
    log.info("ingest runner started")

    stop = asyncio.Event()

    def _sig(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except NotImplementedError:
            pass

    await stop.wait()
    log.info("ingest runner stopping")
    sched.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
