"""Train XGBoost min + max delay models on 1500 synthetic rows.

Features per row:
  event_type_idx, severity_num, port_throughput_rank (1-100),
  historical_avg_days, country_risk_score (0-10)

Targets:
  delay_min_days, delay_max_days

Output:
  backend/ml/delay_model_min.pkl
  backend/ml/delay_model_max.pkl
  backend/ml/feature_names.json
"""
from __future__ import annotations

import json
import logging
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
import xgboost as xgb
import joblib

EVENT_TYPES = ["PORT_STRIKE", "WEATHER_EVENT", "FACTORY_CLOSURE",
               "SANCTIONS", "GEOPOLITICAL", "LOGISTICS_DELAY", "OTHER"]
TYPE_HIST = {"PORT_STRIKE": 10, "WEATHER_EVENT": 5, "FACTORY_CLOSURE": 14,
             "SANCTIONS": 30, "GEOPOLITICAL": 14, "LOGISTICS_DELAY": 4, "OTHER": 3}

FEATURE_NAMES = ["event_type_idx", "severity_num", "port_rank",
                 "hist_avg_days", "country_risk"]

OUT_DIR = ROOT / "chainpulse" / "backend" / "ml"
N_ROWS = 1500
SEED = 42


def synth(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    for _ in range(n):
        etype = random.choice(EVENT_TYPES)
        sev = int(rng.integers(1, 5))   # 1..4
        rank = int(rng.integers(1, 101)) # 1..100
        hist = TYPE_HIST[etype] + rng.normal(0, 1.5)
        risk = float(rng.uniform(0.5, 9.5))
        # ground-truth delay = noisy function of features
        base = hist * sev * 0.45
        rank_factor = 1.0 - (rank - 1) * 0.007
        d_min = max(1.0, base * rank_factor + risk * 0.25 + rng.normal(0, 1.0))
        d_max = max(d_min + 1, base * rank_factor * 2.0 + risk * 0.7 + rng.normal(0, 1.6))
        rows.append({
            "event_type_idx": EVENT_TYPES.index(etype),
            "severity_num": sev,
            "port_rank": rank,
            "hist_avg_days": float(hist),
            "country_risk": risk,
            "delay_min": float(d_min),
            "delay_max": float(d_max),
        })
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log = logging.getLogger("train")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = synth(N_ROWS)
    X = df[FEATURE_NAMES].values
    y_min = df["delay_min"].values
    y_max = df["delay_max"].values

    Xtr, Xte, ymin_tr, ymin_te, ymax_tr, ymax_te = train_test_split(
        X, y_min, y_max, test_size=0.2, random_state=SEED
    )

    common = dict(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.9, random_state=SEED,
        objective="reg:squarederror",
    )

    m_min = xgb.XGBRegressor(**common).fit(Xtr, ymin_tr)
    m_max = xgb.XGBRegressor(**common).fit(Xtr, ymax_tr)

    mae_min = mean_absolute_error(ymin_te, m_min.predict(Xte))
    mae_max = mean_absolute_error(ymax_te, m_max.predict(Xte))
    log.info("MAE min=%.2f  MAE max=%.2f", mae_min, mae_max)

    joblib.dump(m_min, OUT_DIR / "delay_model_min.pkl")
    joblib.dump(m_max, OUT_DIR / "delay_model_max.pkl")
    (OUT_DIR / "feature_names.json").write_text(json.dumps(FEATURE_NAMES))
    log.info("✅ saved %s, %s", OUT_DIR / "delay_model_min.pkl", OUT_DIR / "delay_model_max.pkl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
