"""Neo4j driver singleton + base seed."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from neo4j import Driver, GraphDatabase

from chainpulse.backend.config.settings import get_settings


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    s = get_settings()
    return GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))


@contextmanager
def session():
    driver = get_driver()
    with driver.session() as s:
        yield s


def dispose() -> None:
    try:
        get_driver().close()
    except Exception:
        pass
    get_driver.cache_clear()
