"""Delay predictor — sklearn GBR min + max .pkl if present, else stub formula.

Features (BACKEND_PROMPT module 7):
  event_type, severity, port_throughput_rank, historical_avg_delay, country_risk
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib

from chainpulse.backend.config.settings import get_settings

log = logging.getLogger("chainpulse.delay")

_min_model = None
_max_model = None

# crude port throughput rank (1=biggest)
PORT_RANK = {
    "Port of Shanghai": 1, "Port of Singapore": 2, "Port of Ningbo": 3,
    "Port of Shenzhen": 4, "Port of Guangzhou": 5, "Port of Busan": 6,
    "Port of Hong Kong": 7, "Port of Rotterdam": 10, "Port of Hamburg": 18,
    "Port of Antwerp": 13, "Port of Los Angeles": 17, "Port of Long Beach": 22,
    "Suez Canal": 1, "Panama Canal": 5,
}

# rough country risk score 0-10 (10 = riskiest)
COUNTRY_RISK = {
    "CN": 5, "HK": 4, "TW": 5, "JP": 2, "KR": 3, "SG": 1,
    "US": 3, "CA": 2, "MX": 6, "BR": 6,
    "DE": 2, "NL": 1, "BE": 2, "FR": 3, "GB": 3, "ES": 3, "GR": 4,
    "EG": 7, "AE": 4, "IL": 6, "SA": 5,
    "IN": 5, "VN": 5, "TH": 5, "MY": 4, "ID": 6, "PH": 6,
    "ZA": 6, "RU": 9, "UA": 9, "IR": 9,
}

SEVERITY_NUM = {"critical": 4, "high": 3, "medium": 2, "low": 1}

TYPE_HISTORICAL_DAYS = {
    "PORT_STRIKE": 10, "WEATHER_EVENT": 5, "FACTORY_CLOSURE": 14,
    "SANCTIONS": 30, "GEOPOLITICAL": 14, "LOGISTICS_DELAY": 4, "OTHER": 3,
}


@dataclass
class Features:
    event_type: str
    severity: str
    location_name: str | None
    country_code: str | None


def _model_path(suffix: str) -> Path:
    return Path(get_settings().model_dir) / f"delay_model_{suffix}.pkl"


def _load() -> None:
    global _min_model, _max_model
    for suffix, holder in (("min", "_min_model"), ("max", "_max_model")):
        p = _model_path(suffix)
        if p.exists() and globals()[holder] is None:
            try:
                globals()[holder] = joblib.load(p)
                log.info("loaded %s model", p.name)
            except Exception:
                log.exception("failed to load %s", p)


def _feature_vector(f: Features) -> list[float]:
    rank = PORT_RANK.get(f.location_name or "", 50)
    risk = COUNTRY_RISK.get(f.country_code or "", 5)
    hist = TYPE_HISTORICAL_DAYS.get(f.event_type, 5)
    sev = SEVERITY_NUM.get(f.severity, 1)
    return [hash(f.event_type) % 100, sev, rank, hist, risk]


def _stub(f: Features) -> tuple[int, int, float]:
    sev = SEVERITY_NUM.get(f.severity, 1)
    rank = PORT_RANK.get(f.location_name or "", 50)
    risk = COUNTRY_RISK.get(f.country_code or "", 5)
    hist = TYPE_HISTORICAL_DAYS.get(f.event_type, 5)
    rank_factor = max(0.4, 1.0 - (rank - 1) * 0.01)  # bigger port → larger delay
    min_d = max(1, int(round(hist * sev * 0.4 * rank_factor)))
    max_d = max(min_d + 1, int(round(hist * sev * 0.9 * rank_factor + risk * 0.6)))
    confidence = 0.55 + 0.05 * sev  # cap ~0.75
    return min_d, max_d, round(min(confidence, 0.95), 2)


def predict(f: Features) -> tuple[int, int, float]:
    _load()
    if _min_model is None or _max_model is None:
        return _stub(f)
    import numpy as np
    x = np.array([_feature_vector(f)])
    min_d = max(1, int(round(float(_min_model.predict(x)[0]))))
    max_d = max(min_d + 1, int(round(float(_max_model.predict(x)[0]))))
    return min_d, max_d, 0.81
