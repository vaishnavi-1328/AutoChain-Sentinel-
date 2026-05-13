"""APScheduler wiring — registers all pollers, returns scheduler instance."""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from chainpulse.backend.ingest import gdelt, gnews, guardian, newsapi, rss

log = logging.getLogger("chainpulse.ingest.scheduler")


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    # spec cadences
    sched.add_job(gdelt.poll_once,   "interval", seconds=60,  id="gdelt",    max_instances=1, coalesce=True)
    sched.add_job(rss.poll_once,     "interval", seconds=60,  id="rss",      max_instances=1, coalesce=True)
    sched.add_job(guardian.poll_once,"interval", seconds=120, id="guardian", max_instances=1, coalesce=True)
    sched.add_job(newsapi.poll_once, "interval", seconds=300, id="newsapi",  max_instances=1, coalesce=True)
    sched.add_job(gnews.poll_once,   "interval", seconds=900, id="gnews",    max_instances=1, coalesce=True)
    log.info("scheduler built with 5 pollers")
    return sched
