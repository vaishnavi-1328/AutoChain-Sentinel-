"""SHAP feature contribution explainer for delay models.

Returns per-feature contribution for a given event's prediction.
Cached after first explain call.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from chainpulse.backend.services.delay_predictor import (
    FEATURE_NAMES,
    Features,
    _feature_vector,
    get_models,
)

log = logging.getLogger("chainpulse.shap")

def explain(f: Features) -> dict[str, Any] | None:
    """Returns {features, base_*, predicted_*, contributions:[{name,value,shap_min,shap_max}]}.

    Uses XGBoost native pred_contribs (TreeSHAP) — avoids `shap` lib's stricter parser
    that fails on newer XGBoost JSON format.
    """
    m_min, m_max = get_models()
    if m_min is None or m_max is None:
        return None
    try:
        import xgboost as xgb
        x = np.array([_feature_vector(f)], dtype=float)
        dmat = xgb.DMatrix(x)
        contrib_min = m_min.get_booster().predict(dmat, pred_contribs=True)
        contrib_max = m_max.get_booster().predict(dmat, pred_contribs=True)
        # last column is base (bias). preceding cols = SHAP for each feature.
        sv_min = contrib_min[0, :-1]
        sv_max = contrib_max[0, :-1]
        base_min = float(contrib_min[0, -1])
        base_max = float(contrib_max[0, -1])
    except Exception:
        log.exception("SHAP explain failed")
        return None

    pred_min = float(base_min + sv_min.sum())
    pred_max = float(base_max + sv_max.sum())

    contribs = []
    for i, name in enumerate(FEATURE_NAMES):
        contribs.append({
            "name": name,
            "value": float(x[0, i]),
            "shap_min": float(sv_min[i]),
            "shap_max": float(sv_max[i]),
        })

    return {
        "features": FEATURE_NAMES,
        "base_min": round(base_min, 2),
        "base_max": round(base_max, 2),
        "predicted_min": round(pred_min, 2),
        "predicted_max": round(pred_max, 2),
        "contributions": contribs,
    }
