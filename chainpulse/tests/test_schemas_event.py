"""ProcessedEvent schema validation."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from chainpulse.backend.schemas.event import ProcessedEvent


def test_minimal_processed_event():
    e = ProcessedEvent(
        id="evt_1",
        type="PORT_STRIKE",
        severity="critical",
        title="Port of Shanghai strike",
        timestamp_utc=datetime.now(timezone.utc),
    )
    assert e.ttl_seconds == 300
    assert e.affected_sku_count == 0


def test_rejects_unknown_event_type():
    with pytest.raises(ValidationError):
        ProcessedEvent(
            id="evt_2",
            type="UFO_LANDING",  # type: ignore[arg-type]
            severity="low",
            title="x",
            timestamp_utc=datetime.now(timezone.utc),
        )


def test_rejects_unknown_severity():
    with pytest.raises(ValidationError):
        ProcessedEvent(
            id="evt_3",
            type="PORT_STRIKE",
            severity="catastrophic",  # type: ignore[arg-type]
            title="x",
            timestamp_utc=datetime.now(timezone.utc),
        )
