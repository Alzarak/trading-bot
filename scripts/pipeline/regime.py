"""Macro regime classifier and market top risk scorer with split TTL caching.

Adapts scoring logic from two reference skills:
  - macro-regime-detector: 6 cross-asset ratio calculators + classify_regime()
  - market-top-detector: 6 market condition calculators + composite scoring

When FMP is unavailable, returns neutral defaults:
  regime='transitional', top_risk_score=30.0, risk_zone='green'.

Split TTL cache:
  - MACRO_TTL_SECONDS (3600): hourly refresh for macro regime label
  - TOP_RISK_TTL_SECONDS (900): 15-minute refresh for top_risk intraday score
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from scripts.models import RegimeState
from scripts.pipeline.fmp_client import FMPClient

# ---------------------------------------------------------------------------
# TTL constants (D-04 locked)
# ---------------------------------------------------------------------------

MACRO_TTL_SECONDS = 3600    # hourly refresh for macro regime label
TOP_RISK_TTL_SECONDS = 900  # 15-min refresh for top_risk intraday score

# ---------------------------------------------------------------------------
# FMP symbols fetched for regime calculations
# ---------------------------------------------------------------------------

_REGIME_SYMBOLS = ["SPY", "IWM", "RSP", "HYG", "LQD", "TLT", "XLY", "XLP"]

# Additional ETFs for top-risk defensive rotation check
_DEFENSIVE_ETFS = ["XLU", "XLP", "XLV", "VNQ"]
_OFFENSIVE_ETFS = ["XLK", "XLC", "XLY", "QQQ"]

# ---------------------------------------------------------------------------
# Zone thresholds for risk_zone mapping — MUST store bare color string
# ---------------------------------------------------------------------------

ZONE_THRESHOLDS = [
    (0,   20,  "green"),    # Normal market conditions
    (20,  40,  "yellow"),   # Early warning
    (40,  60,  "orange"),   # Elevated risk
    (60,  80,  "red"),      # High probability top
    (80,  100, "critical"), # Extreme risk / likely top
]

# ---------------------------------------------------------------------------
# Component weights (macro regime)
# ---------------------------------------------------------------------------

_MACRO_WEIGHTS = {
    "concentration": 0.25,
    "yield_curve":   0.20,
    "credit_conditions": 0.15,
    "size_factor":   0.15,
    "equity_bond":   0.15,
    "sector_rotation": 0.10,
}

# Component weights (market top risk)
_TOP_RISK_WEIGHTS = {
    "distribution_days":  0.25,
    "leading_stocks":     0.20,
    "defensive_rotation": 0.15,
    "breadth_divergence": 0.15,
    "index_technical":    0.15,
    "sentiment":          0.10,
}

# ---------------------------------------------------------------------------
# Helper: FMP response → daily history list
# ---------------------------------------------------------------------------

def _extract_history(fmp_response: Optional[dict], symbol: str) -> list[dict]:
    """Extract 'historical' list from FMP get_historical_prices() response."""
    if not fmp_response:
        return []
    historical = fmp_response.get("historical", [])
    if not isinstance(historical, list):
        return []
    return historical  # FMP returns most recent first


# ---------------------------------------------------------------------------
# Shared utility functions (adapted from macro-regime-detector/utils.py)
# ---------------------------------------------------------------------------

def _downsample_to_monthly(daily_history: list[dict]) -> list[dict]:
    """Downsample daily OHLCV to monthly (most recent bar per month, most recent first)."""
    if not daily_history:
        return []
    monthly: dict[str, dict] = {}
    for bar in daily_history:
        date_str = bar.get("date", "")
        close = bar.get("adjClose", bar.get("close", 0))
        if not date_str or close == 0:
            continue
        ym = date_str[:7]
        if ym not in monthly:
            monthly[ym] = {"date": date_str, "close": close}
    return sorted(monthly.values(), key=lambda x: x["date"], reverse=True)


def _calculate_ratio(num: list[dict], den: list[dict]) -> list[dict]:
    """Compute ratio of two monthly series aligned by YYYY-MM key."""
    denom_lookup: dict[str, float] = {}
    for bar in den:
        ym = bar["date"][:7]
        denom_lookup[ym] = bar["close"]
    result = []
    for bar in num:
        ym = bar["date"][:7]
        if ym in denom_lookup and denom_lookup[ym] != 0:
            result.append({"date": bar["date"], "value": bar["close"] / denom_lookup[ym]})
    return result


def _compute_sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[:period]) / period


def _compute_roc(values: list[float], period: int) -> Optional[float]:
    if len(values) <= period:
        return None
    past = values[period]
    if past == 0:
        return None
    return (values[0] - past) / past * 100


def _detect_crossover(values: list[float], short_period: int = 6, long_period: int = 12) -> dict:
    if len(values) < long_period + 3:
        return {"type": "none", "bars_ago": None, "gap_pct": None}
    max_lookback = min(len(values), long_period + 12)
    sma_pairs = []
    for offset in range(max_lookback - long_period + 1):
        subset = values[offset:]
        short_sma = _compute_sma(subset, short_period)
        long_sma = _compute_sma(subset, long_period)
        if short_sma is not None and long_sma is not None:
            sma_pairs.append((short_sma, long_sma))
    if len(sma_pairs) < 2:
        return {"type": "none", "bars_ago": None, "gap_pct": None}
    current_short, current_long = sma_pairs[0]
    gap_pct = (current_short - current_long) / current_long * 100 if current_long != 0 else 0
    for i in range(1, len(sma_pairs)):
        prev_short, prev_long = sma_pairs[i]
        curr_short, curr_long = sma_pairs[i - 1]
        if prev_short <= prev_long and curr_short > curr_long:
            return {"type": "golden_cross", "bars_ago": i - 1, "gap_pct": round(gap_pct, 3)}
        if prev_short >= prev_long and curr_short < curr_long:
            return {"type": "death_cross", "bars_ago": i - 1, "gap_pct": round(gap_pct, 3)}
    if abs(gap_pct) < 1.0:
        return {"type": "converging", "bars_ago": None, "gap_pct": round(gap_pct, 3)}
    return {"type": "none", "bars_ago": None, "gap_pct": round(gap_pct, 3)}


def _score_transition_signal(
    crossover: dict,
    roc_short: Optional[float],
    roc_long: Optional[float],
    sma_short: Optional[float],
    sma_long: Optional[float],
) -> int:
    """Score transition signal strength 0-100 from crossover + momentum."""
    score = 0
    cross_type = crossover.get("type", "none")
    bars_ago = crossover.get("bars_ago")
    gap_pct = crossover.get("gap_pct", 0) or 0

    if cross_type in ("golden_cross", "death_cross"):
        if bars_ago is not None and bars_ago <= 2:
            score += 40
        elif bars_ago is not None and bars_ago <= 5:
            score += 30
        else:
            score += 20
    elif cross_type == "converging":
        closeness = max(0, 1.0 - abs(gap_pct)) * 25
        score += int(closeness)

    if roc_short is not None and roc_long is not None:
        if (roc_long < 0 and roc_short > 0) or (roc_long > 0 and roc_short < 0):
            strength = min(abs(roc_short), 5.0) / 5.0 * 30
            score += int(strength)
        elif abs(roc_short) > 3.0:
            score += 10

    signals_aligned = 0
    if cross_type in ("golden_cross", "death_cross"):
        signals_aligned += 1
    if cross_type == "golden_cross" and roc_short is not None and roc_short > 0:
        signals_aligned += 1
    elif cross_type == "death_cross" and roc_short is not None and roc_short < 0:
        signals_aligned += 1
    if sma_short is not None and sma_long is not None and sma_long != 0:
        current_gap = abs(sma_short - sma_long) / sma_long * 100
        if current_gap > 0.5:
            signals_aligned += 1
    score += signals_aligned * 10
    return min(100, max(0, score))


def _determine_direction(
    crossover: dict,
    roc_3m: Optional[float],
    positive_label: str,
    negative_label: str,
    neutral_label: str = "neutral",
) -> tuple[str, str]:
    """Determine direction string from crossover and 3m momentum."""
    _STALE = 3
    cross_type = crossover.get("type", "none")
    bars_ago = crossover.get("bars_ago")
    is_stale = bars_ago is not None and bars_ago >= _STALE

    cross_dir: Optional[str] = None
    if cross_type == "golden_cross":
        cross_dir = positive_label
    elif cross_type == "death_cross":
        cross_dir = negative_label

    mom_dir: Optional[str] = None
    if roc_3m is not None and roc_3m > 0:
        mom_dir = positive_label
    elif roc_3m is not None and roc_3m < 0:
        mom_dir = negative_label

    if cross_dir:
        if is_stale and mom_dir and mom_dir != cross_dir:
            return mom_dir, "reversing"
        qualifier = (
            "confirmed" if mom_dir == cross_dir
            else "fading" if mom_dir and mom_dir != cross_dir
            else "N/A"
        )
        return cross_dir, qualifier
    elif mom_dir:
        return mom_dir, "N/A"
    return neutral_label, "N/A"


def _compute_rolling_correlation(
    series_a: list[float], series_b: list[float], window: int
) -> Optional[float]:
    if len(series_a) < window or len(series_b) < window:
        return None
    a = series_a[:window]
    b = series_b[:window]
    n = window
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
    std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
    std_b = (sum((x - mean_b) ** 2 for x in b) / n) ** 0.5
    if std_a == 0 or std_b == 0:
        return 0.0
    return cov / (std_a * std_b)


# ---------------------------------------------------------------------------
# Macro regime: 6 component calculators (adapted inline from skill)
# ---------------------------------------------------------------------------

def _calc_ratio_component(
    num_history: list[dict],
    den_history: list[dict],
    positive_label: str,
    negative_label: str,
    neutral_label: str = "neutral",
) -> dict:
    """Generic ratio-based component scorer used by concentration, size, credit, sector."""
    if not num_history or not den_history:
        return {"score": 0, "data_available": False, "direction": "unknown"}
    num_monthly = _downsample_to_monthly(num_history)
    den_monthly = _downsample_to_monthly(den_history)
    if len(num_monthly) < 12 or len(den_monthly) < 12:
        return {"score": 0, "data_available": False, "direction": "unknown"}
    ratio_series = _calculate_ratio(num_monthly, den_monthly)
    if len(ratio_series) < 12:
        return {"score": 0, "data_available": False, "direction": "unknown"}
    ratio_values = [r["value"] for r in ratio_series]
    sma_6m = _compute_sma(ratio_values, 6)
    sma_12m = _compute_sma(ratio_values, 12)
    crossover = _detect_crossover(ratio_values)
    roc_3m = _compute_roc(ratio_values, 3)
    roc_12m = _compute_roc(ratio_values, 12)
    score = _score_transition_signal(crossover, roc_3m, roc_12m, sma_6m, sma_12m)
    direction, _ = _determine_direction(crossover, roc_3m, positive_label, negative_label, neutral_label)
    return {"score": score, "data_available": True, "direction": direction}


def _calc_concentration(histories: dict[str, list[dict]]) -> dict:
    """RSP/SPY ratio — broadening vs concentrating."""
    result = _calc_ratio_component(
        histories.get("RSP", []),
        histories.get("SPY", []),
        positive_label="broadening",
        negative_label="concentrating",
        neutral_label="neutral",
    )
    # concentration_calculator uses SMA fallback for direction when no crossover
    if result.get("data_available") and result.get("direction") == "neutral":
        rsp_m = _downsample_to_monthly(histories.get("RSP", []))
        spy_m = _downsample_to_monthly(histories.get("SPY", []))
        if len(rsp_m) >= 12 and len(spy_m) >= 12:
            ratio_values = [r["value"] for r in _calculate_ratio(rsp_m, spy_m)]
            sma_6 = _compute_sma(ratio_values, 6)
            sma_12 = _compute_sma(ratio_values, 12)
            if sma_6 is not None and sma_12 is not None:
                result["direction"] = "broadening" if sma_6 > sma_12 else "concentrating"
    return result


def _calc_size_factor(histories: dict[str, list[dict]]) -> dict:
    """IWM/SPY ratio — small_cap_leading vs large_cap_leading."""
    return _calc_ratio_component(
        histories.get("IWM", []),
        histories.get("SPY", []),
        positive_label="small_cap_leading",
        negative_label="large_cap_leading",
        neutral_label="neutral",
    )


def _calc_credit_conditions(histories: dict[str, list[dict]]) -> dict:
    """HYG/LQD ratio — easing vs tightening."""
    return _calc_ratio_component(
        histories.get("HYG", []),
        histories.get("LQD", []),
        positive_label="easing",
        negative_label="tightening",
        neutral_label="stable",
    )


def _calc_sector_rotation(histories: dict[str, list[dict]]) -> dict:
    """XLY/XLP ratio — risk_on vs risk_off."""
    return _calc_ratio_component(
        histories.get("XLY", []),
        histories.get("XLP", []),
        positive_label="risk_on",
        negative_label="risk_off",
        neutral_label="neutral",
    )


def _calc_equity_bond(histories: dict[str, list[dict]]) -> dict:
    """SPY/TLT ratio + stock-bond correlation."""
    spy_h = histories.get("SPY", [])
    tlt_h = histories.get("TLT", [])
    if not spy_h or not tlt_h:
        return {"score": 0, "data_available": False, "direction": "unknown", "correlation_regime": "unknown"}
    spy_m = _downsample_to_monthly(spy_h)
    tlt_m = _downsample_to_monthly(tlt_h)
    if len(spy_m) < 12 or len(tlt_m) < 12:
        return {"score": 0, "data_available": False, "direction": "unknown", "correlation_regime": "unknown"}
    ratio_series = _calculate_ratio(spy_m, tlt_m)
    if len(ratio_series) < 12:
        return {"score": 0, "data_available": False, "direction": "unknown", "correlation_regime": "unknown"}
    ratio_values = [r["value"] for r in ratio_series]
    sma_6m = _compute_sma(ratio_values, 6)
    sma_12m = _compute_sma(ratio_values, 12)
    crossover = _detect_crossover(ratio_values)
    roc_3m = _compute_roc(ratio_values, 3)
    roc_12m = _compute_roc(ratio_values, 12)
    ratio_score = _score_transition_signal(crossover, roc_3m, roc_12m, sma_6m, sma_12m)

    # Monthly returns for rolling correlation
    spy_closes = [m["close"] for m in spy_m]
    tlt_closes = [m["close"] for m in tlt_m]
    spy_rets = [
        (spy_closes[i] - spy_closes[i + 1]) / spy_closes[i + 1]
        for i in range(len(spy_closes) - 1)
        if spy_closes[i + 1] != 0
    ]
    tlt_rets = [
        (tlt_closes[i] - tlt_closes[i + 1]) / tlt_closes[i + 1]
        for i in range(len(tlt_closes) - 1)
        if tlt_closes[i + 1] != 0
    ]
    corr_6m = _compute_rolling_correlation(spy_rets, tlt_rets, 6)
    corr_12m = _compute_rolling_correlation(spy_rets, tlt_rets, 12)

    # Correlation regime
    corr_regime = "unknown"
    if corr_6m is not None:
        if corr_6m < -0.3:
            corr_regime = "negative_strong"
        elif corr_6m < 0:
            corr_regime = "negative_mild"
        elif corr_6m < 0.3:
            corr_regime = "near_zero"
        else:
            corr_regime = "positive"

    # Correlation transition bonus
    corr_bonus = 0
    if corr_6m is not None and corr_12m is not None:
        if (corr_6m > 0) != (corr_12m > 0):
            corr_bonus = 20
        elif abs(corr_6m - corr_12m) > 0.3:
            corr_bonus = 10

    score = min(100, ratio_score + corr_bonus)
    direction, _ = _determine_direction(crossover, roc_3m, "risk_on", "risk_off", "neutral")
    return {
        "score": score,
        "data_available": True,
        "direction": direction,
        "correlation_regime": corr_regime,
    }


def _calc_yield_curve(treasury_rates: Optional[list]) -> dict:
    """10Y-2Y treasury spread analysis."""
    if not treasury_rates:
        return {"score": 0, "data_available": False, "direction": "unknown"}
    spread_monthly: dict[str, dict] = {}
    for entry in treasury_rates:
        date_str = entry.get("date", "")
        year10 = entry.get("year10")
        year2 = entry.get("year2")
        if not date_str or year10 is None or year2 is None:
            continue
        try:
            y10, y2 = float(year10), float(year2)
        except (ValueError, TypeError):
            continue
        ym = date_str[:7]
        if ym not in spread_monthly:
            spread_monthly[ym] = {"date": date_str, "spread": y10 - y2}
    if len(spread_monthly) < 12:
        return {"score": 0, "data_available": False, "direction": "unknown"}
    spread_series = sorted(spread_monthly.values(), key=lambda x: x["date"], reverse=True)
    spread_values = [s["spread"] for s in spread_series]
    sma_6m = _compute_sma(spread_values, 6)
    sma_12m = _compute_sma(spread_values, 12)
    crossover = _detect_crossover(spread_values)
    roc_3m = _compute_roc(spread_values, 3)
    roc_12m = _compute_roc(spread_values, 12)
    score = _score_transition_signal(crossover, roc_3m, roc_12m, sma_6m, sma_12m)
    direction = (
        "steepening" if roc_3m is not None and roc_3m > 0
        else "flattening" if roc_3m is not None and roc_3m < 0
        else "stable"
    )
    return {"score": score, "data_available": True, "direction": direction}


# ---------------------------------------------------------------------------
# Macro regime classification (adapted from macro-regime-detector/scorer.py)
# ---------------------------------------------------------------------------

def _classify_regime(component_results: dict[str, dict]) -> tuple[str, float]:
    """Classify macro regime from 6 component results. Returns (regime, confidence)."""

    def _dir(comp: dict) -> str:
        if not comp.get("data_available", False):
            return "unknown"
        return comp.get("direction", "unknown")

    conc_dir = _dir(component_results.get("concentration", {}))
    yc_dir = _dir(component_results.get("yield_curve", {}))
    credit_dir = _dir(component_results.get("credit_conditions", {}))
    size_dir = _dir(component_results.get("size_factor", {}))
    eb_dir = _dir(component_results.get("equity_bond", {}))
    sector_dir = _dir(component_results.get("sector_rotation", {}))
    corr_regime = (
        component_results.get("equity_bond", {}).get("correlation_regime", "unknown")
        if component_results.get("equity_bond", {}).get("data_available", False)
        else "unknown"
    )

    available_count = sum(
        1 for k in ["concentration", "yield_curve", "credit_conditions", "size_factor", "equity_bond", "sector_rotation"]
        if component_results.get(k, {}).get("data_available", False)
    )

    # Score each regime hypothesis
    def _score_concentration() -> int:
        s = 0
        if conc_dir == "concentrating":
            s += 2
        if size_dir == "large_cap_leading":
            s += 2
        if credit_dir in ("stable", "easing"):
            s += 1
        return s

    def _score_broadening() -> int:
        s = 0
        if conc_dir == "broadening":
            s += 2
        if size_dir == "small_cap_leading":
            s += 2
        if credit_dir in ("stable", "easing"):
            s += 1
        if sector_dir == "risk_on":
            s += 1
        if yc_dir == "steepening":
            s += 1
        return s

    def _score_contraction() -> int:
        s = 0
        if credit_dir == "tightening":
            s += 2
        if sector_dir == "risk_off":
            s += 2
        if eb_dir == "risk_off":
            s += 1
        if yc_dir == "flattening":
            s += 1
        if size_dir == "small_cap_leading":
            s -= 1
        return max(0, s)

    def _score_inflationary() -> int:
        s = 0
        if corr_regime == "positive":
            s += 3
        elif corr_regime == "near_zero":
            s += 1
        if eb_dir == "risk_off":
            s += 1
        return s

    regime_scores = {
        "concentration": _score_concentration(),
        "broadening":    _score_broadening(),
        "contraction":   _score_contraction(),
        "inflationary":  _score_inflationary(),
    }

    # Count signaling components
    all_scores_list = [
        component_results.get(k, {}).get("score", 0)
        for k in ["concentration", "yield_curve", "credit_conditions", "size_factor", "equity_bond", "sector_rotation"]
    ]
    signaling = sum(1 for s in all_scores_list if s >= 40)

    sorted_regimes = sorted(regime_scores.items(), key=lambda x: x[1], reverse=True)
    best_regime = sorted_regimes[0][0]
    best_score = sorted_regimes[0][1]

    # Tiebreak detection
    is_tied = (
        len(sorted_regimes) >= 2
        and best_score > 0
        and (best_score - sorted_regimes[1][1]) <= 1
    )

    # Quick composite for tiebreak
    quick_composite = sum(
        component_results.get(k, {}).get("score", 0) * w
        for k, w in _MACRO_WEIGHTS.items()
    )

    if is_tied and quick_composite < 50:
        best_regime = "transitional"
    elif signaling >= 3 and best_score < 3:
        best_regime = "transitional"
        best_score = signaling

    # Confidence level
    if best_score >= 4:
        confidence_str = "high"
    elif best_score >= 3:
        confidence_str = "moderate"
    elif best_score >= 2:
        confidence_str = "low"
    else:
        confidence_str = "very_low"

    if is_tied and confidence_str == "high":
        confidence_str = "moderate"
    if available_count <= 3:
        confidence_str = "very_low"
    elif available_count <= 4 and confidence_str in ("high", "moderate"):
        confidence_str = "low"

    confidence_map = {"high": 0.9, "moderate": 0.6, "low": 0.35, "very_low": 0.1}
    confidence_float = confidence_map.get(confidence_str, 0.1)

    return best_regime, confidence_float


# ---------------------------------------------------------------------------
# Top-risk: 6 component calculators (adapted inline from market-top-detector)
# ---------------------------------------------------------------------------

def _calc_ema(closes: list[float], period: int) -> float:
    """EMA calculation from most-recent-first close list."""
    if len(closes) < period:
        return closes[0] if closes else 0.0
    # Work oldest-first for EMA
    reversed_closes = list(reversed(closes))
    k = 2.0 / (period + 1)
    ema = reversed_closes[0]
    for price in reversed_closes[1:]:
        ema = price * k + ema * (1 - k)
    return ema


def _top_risk_distribution_days(spy_history: list[dict], qqq_history: list[dict]) -> dict:
    """Count distribution days in the last 25 trading days for SPY and QQQ."""
    def _count(history: list[dict]) -> float:
        if not history or len(history) < 2:
            return 0.0
        dist = 0
        stall = 0
        window = min(25, len(history) - 1)
        for i in range(window):
            today = history[i]
            yesterday = history[i + 1]
            t_close = today.get("adjClose", today.get("close", 0))
            y_close = yesterday.get("adjClose", yesterday.get("close", 0))
            t_vol = today.get("volume", 0)
            y_vol = yesterday.get("volume", 0)
            if y_close == 0 or y_vol == 0:
                continue
            pct = (t_close - y_close) / y_close * 100
            vol_up = t_vol > y_vol
            if pct <= -0.2 and vol_up:
                dist += 1
            elif vol_up and 0 <= pct < 0.1:
                stall += 1
        return dist + 0.5 * stall

    spy_eff = _count(spy_history)
    qqq_eff = _count(qqq_history)
    effective = max(spy_eff, qqq_eff)

    if effective >= 6:
        score = 100
    elif effective >= 5:
        score = 90
    elif effective >= 4:
        score = 75
    elif effective >= 3:
        score = 55
    elif effective >= 2:
        score = 30
    elif effective >= 1:
        score = 15
    else:
        score = 0

    return {"score": score, "effective_count": effective, "data_available": bool(spy_history or qqq_history)}


def _top_risk_index_technical(spy_history: list[dict]) -> dict:
    """Evaluate SPY technical condition (MA, trend checks)."""
    if not spy_history or len(spy_history) < 21:
        return {"score": 0, "data_available": False}
    closes = [d.get("adjClose", d.get("close", 0)) for d in spy_history]
    highs = [d.get("high", d.get("close", 0)) for d in spy_history]
    volumes = [d.get("volume", 0) for d in spy_history]
    price = closes[0]
    score = 0

    ema21 = _calc_ema(closes, 21)
    if price < ema21:
        score += 8

    ema50 = _calc_ema(closes, 50) if len(closes) >= 50 else None
    if ema50 and price < ema50:
        score += 12
    if ema50 and ema21 < ema50:
        score += 10

    if len(closes) >= 200:
        sma200 = sum(closes[:200]) / 200
        if price < sma200:
            score += 15

    # Failed rally: peak 3-10 days ago and price dropped >2%
    if len(closes) >= 15:
        recent = closes[:15]
        peak_idx = recent.index(max(recent))
        if 3 <= peak_idx <= 10:
            drop = (recent[0] - recent[peak_idx]) / recent[peak_idx] * 100
            if drop < -2.0:
                score += 10

    # Lower highs (20-day)
    if len(highs) >= 20:
        swing_highs = []
        rh = highs[:20]
        for i in range(1, len(rh) - 1):
            if rh[i] > rh[i - 1] and rh[i] > rh[i + 1]:
                swing_highs.append(rh[i])
        if len(swing_highs) >= 2 and swing_highs[0] < swing_highs[1]:
            score += 10

    return {"score": min(100, score), "data_available": True}


def _top_risk_leading_stocks(spy_history: list[dict], iwm_history: list[dict]) -> dict:
    """Proxy leading stock health: SPY + IWM position vs 50/200 DMA and distance from high."""
    score = 0
    has_data = False
    for hist in [spy_history, iwm_history]:
        if not hist or len(hist) < 20:
            continue
        has_data = True
        closes = [d.get("adjClose", d.get("close", 0)) for d in hist]
        price = closes[0]
        year_high = max(closes[:min(252, len(closes))])
        distance_pct = (price - year_high) / year_high * 100 if year_high > 0 else 0
        # Distance from 52-week high
        if distance_pct <= -25:
            score += 20
        elif distance_pct <= -15:
            score += 15
        elif distance_pct <= -10:
            score += 10
        elif distance_pct <= -5:
            score += 5
        # Position vs 50DMA
        if len(closes) >= 50:
            sma50 = sum(closes[:50]) / 50
            if price < sma50:
                score += 10
    if not has_data:
        return {"score": 0, "data_available": False}
    return {"score": min(100, score), "data_available": True}


def _top_risk_defensive_rotation(all_histories: dict[str, list[dict]]) -> dict:
    """Defensive (XLU, XLP, XLV, VNQ) vs offensive (XLK, XLC, XLY, QQQ) 20-day returns."""
    def _ret(hist: list[dict], days: int) -> Optional[float]:
        if not hist or len(hist) < days + 1:
            return None
        recent = hist[0].get("adjClose", hist[0].get("close", 0))
        past = hist[days].get("adjClose", hist[days].get("close", 0))
        if past == 0:
            return None
        return (recent - past) / past * 100

    def_rets = [_ret(all_histories.get(s, []), 20) for s in _DEFENSIVE_ETFS]
    off_rets = [_ret(all_histories.get(s, []), 20) for s in _OFFENSIVE_ETFS]
    def_rets = [r for r in def_rets if r is not None]
    off_rets = [r for r in off_rets if r is not None]

    if not def_rets or not off_rets:
        return {"score": 0, "data_available": False}

    relative = sum(def_rets) / len(def_rets) - sum(off_rets) / len(off_rets)
    if relative >= 5.0:
        score = 100
    elif relative >= 3.0:
        score = round(80 + (relative - 3.0) / 2.0 * 20)
    elif relative >= 1.5:
        score = round(60 + (relative - 1.5) / 1.5 * 20)
    elif relative >= 0.5:
        score = round(40 + (relative - 0.5) / 1.0 * 20)
    elif relative >= 0.0:
        score = round(20 + relative / 0.5 * 20)
    elif relative >= -2.0:
        score = round(max(0, 20 + relative / 2.0 * 20))
    else:
        score = 0

    return {"score": max(0, min(100, score)), "data_available": True}


def _top_risk_breadth_divergence(spy_history: list[dict]) -> dict:
    """Proxy breadth: % of SPY in last 252 days above their 50-day SMA using SPY itself."""
    # Without breadth data access (FMP doesn't expose it), score neutral 30 (slightly healthy)
    if not spy_history or len(spy_history) < 50:
        return {"score": 30, "data_available": False}
    closes = [d.get("adjClose", d.get("close", 0)) for d in spy_history]
    price = closes[0]
    sma50 = sum(closes[:50]) / 50
    year_high = max(closes[:min(252, len(closes))])
    distance_from_high = (price - year_high) / year_high * 100 if year_high > 0 else 0
    near_highs = distance_from_high >= -5.0

    # Use SPY's own position relative to MA as a rough breadth proxy
    # Above 50DMA and near highs -> healthy breadth (low score)
    # Below 50DMA and near highs -> divergence warning
    if near_highs:
        if price < sma50:
            score = 60  # Price near high but below MA = divergence
        elif price < sma50 * 1.02:
            score = 35
        else:
            score = 10  # Healthy
    else:
        # Not near highs — halve breadth score relevance
        if price < sma50:
            score = 30
        else:
            score = 10

    return {"score": score, "data_available": True}


def _top_risk_sentiment(spy_history: list[dict]) -> dict:
    """Sentiment proxy from SPY volatility (lack of VIX data without separate endpoint)."""
    # Without VIX data, use SPY's realized volatility as proxy
    if not spy_history or len(spy_history) < 20:
        return {"score": 0, "data_available": False}
    closes = [d.get("adjClose", d.get("close", 0)) for d in spy_history[:20]]
    if len(closes) < 2:
        return {"score": 0, "data_available": False}
    returns = [
        abs((closes[i] - closes[i + 1]) / closes[i + 1] * 100)
        for i in range(len(closes) - 1)
        if closes[i + 1] != 0
    ]
    if not returns:
        return {"score": 0, "data_available": False}
    avg_daily_move = sum(returns) / len(returns)
    # Low volatility = complacency (higher risk score)
    # High volatility = fear already present (lower top risk)
    if avg_daily_move < 0.3:
        score = 25   # Very low vol = complacency
    elif avg_daily_move < 0.6:
        score = 17
    elif avg_daily_move < 1.0:
        score = 8
    elif avg_daily_move < 2.0:
        score = 0    # Normal vol
    else:
        score = 0    # High vol = fear present, top less likely

    return {"score": score, "data_available": True}


# ---------------------------------------------------------------------------
# Zone mapping helper
# ---------------------------------------------------------------------------

def _score_to_zone(score: float) -> str:
    """Map composite 0-100 score to bare color zone string."""
    for low, high, color in ZONE_THRESHOLDS:
        if low <= score <= high:
            return color
    return "critical"


# ---------------------------------------------------------------------------
# Macro composite scorer (adapted from macro-regime-detector/scorer.py)
# ---------------------------------------------------------------------------

def _macro_composite_score(component_results: dict[str, dict]) -> float:
    """Weighted composite of 6 macro component scores."""
    composite = 0.0
    for key, weight in _MACRO_WEIGHTS.items():
        score = component_results.get(key, {}).get("score", 0)
        composite += score * weight
    return round(composite, 1)


# ---------------------------------------------------------------------------
# Top-risk composite scorer (adapted from market-top-detector/scorer.py)
# ---------------------------------------------------------------------------

def _top_risk_composite_score(component_results: dict[str, dict]) -> float:
    """Weighted composite of 6 top-risk component scores."""
    composite = 0.0
    for key, weight in _TOP_RISK_WEIGHTS.items():
        score = component_results.get(key, {}).get("score", 0)
        composite += score * weight
    return round(composite, 1)


# ---------------------------------------------------------------------------
# RegimeDetector
# ---------------------------------------------------------------------------

class RegimeDetector:
    """Macro regime classifier and market top risk scorer.

    Accepts an FMPClient instance. When FMP is disabled, returns transitional
    defaults on every detect() call. When enabled, lazily refreshes macro regime
    (hourly) and top_risk score (every 15 minutes) via split TTL caching.

    Usage:
        fmp = FMPClient()
        detector = RegimeDetector(fmp)
        state: RegimeState = detector.detect()
    """

    def __init__(self, fmp_client: FMPClient) -> None:
        self._fmp = fmp_client
        # Split TTL timestamps
        self._macro_cached_at: datetime | None = None
        self._top_risk_cached_at: datetime | None = None
        # Cached values — D-01 locked defaults
        self._cached_regime: str = "transitional"
        self._cached_regime_confidence: float = 0.0
        self._cached_top_risk: float = 30.0   # MUST be 30.0, not 50 — D-01
        self._cached_risk_zone: str = "green"
        self._cached_components: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self) -> RegimeState:
        """Return current RegimeState, refreshing caches when TTLs expire.

        Never raises — all exceptions are caught inside refresh methods.
        Returns neutral defaults when FMP unavailable.
        """
        now = datetime.utcnow()
        macro_stale = (
            self._macro_cached_at is None
            or (now - self._macro_cached_at).total_seconds() > MACRO_TTL_SECONDS
        )
        top_risk_stale = (
            self._top_risk_cached_at is None
            or (now - self._top_risk_cached_at).total_seconds() > TOP_RISK_TTL_SECONDS
        )

        if macro_stale:
            self._refresh_macro()
        else:
            logger.debug("Regime cache hit — macro regime: {} (confidence={:.2f})",
                         self._cached_regime, self._cached_regime_confidence)

        if top_risk_stale:
            self._refresh_top_risk()
        else:
            logger.debug("Regime cache hit — top_risk={:.0f}, zone={}",
                         self._cached_top_risk, self._cached_risk_zone)

        return RegimeState(
            regime=self._cached_regime,           # type: ignore[arg-type]
            regime_confidence=self._cached_regime_confidence,
            top_risk_score=self._cached_top_risk,
            risk_zone=self._cached_risk_zone,      # type: ignore[arg-type]
            cached_at=now,
            components=self._cached_components.copy(),
        )

    # ------------------------------------------------------------------
    # Private refresh methods
    # ------------------------------------------------------------------

    def _refresh_macro(self) -> None:
        """Refresh macro regime label. Hourly TTL (MACRO_TTL_SECONDS=3600).

        On FMP failure or exception, leaves cached values unchanged.
        """
        if not self._fmp._enabled:
            logger.debug("FMP unavailable — macro regime using defaults (transitional/30)")
            return
        try:
            # Fetch price history for all regime symbols
            histories: dict[str, list[dict]] = {}
            for symbol in _REGIME_SYMBOLS:
                resp = self._fmp.get_historical_prices(symbol, days=600)
                histories[symbol] = _extract_history(resp, symbol)

            # Fetch treasury rates for yield curve
            treasury_rates = self._fmp.get_treasury_rates(days=600)

            # Compute 6 component results
            component_results = {
                "concentration":   _calc_concentration(histories),
                "size_factor":     _calc_size_factor(histories),
                "credit_conditions": _calc_credit_conditions(histories),
                "sector_rotation": _calc_sector_rotation(histories),
                "equity_bond":     _calc_equity_bond(histories),
                "yield_curve":     _calc_yield_curve(treasury_rates),
            }

            # Classify regime
            regime, confidence = _classify_regime(component_results)
            composite = _macro_composite_score(component_results)

            # Update cache
            self._cached_regime = regime
            self._cached_regime_confidence = confidence
            self._macro_cached_at = datetime.utcnow()
            self._cached_components.update({
                "macro": {k: {"score": v.get("score", 0), "direction": v.get("direction", "unknown")}
                          for k, v in component_results.items()},
                "macro_composite": composite,
            })
            logger.info(
                "Macro regime refreshed: {} (confidence={:.2f}, composite={:.0f})",
                regime, confidence, composite,
            )
        except Exception as exc:
            logger.warning("Macro regime refresh failed: {} — using cached/default values", exc)

    def _refresh_top_risk(self) -> None:
        """Refresh top-risk score. 15-minute TTL (TOP_RISK_TTL_SECONDS=900).

        On FMP failure or exception, leaves cached values unchanged.
        """
        if not self._fmp._enabled:
            return
        try:
            # Fetch SPY, IWM for core technicals
            spy_resp = self._fmp.get_historical_prices("SPY", days=300)
            iwm_resp = self._fmp.get_historical_prices("IWM", days=300)
            spy_history = _extract_history(spy_resp, "SPY")
            iwm_history = _extract_history(iwm_resp, "IWM")

            # Fetch defensive/offensive ETF histories for rotation check
            rotation_histories: dict[str, list[dict]] = {}
            for symbol in _DEFENSIVE_ETFS + _OFFENSIVE_ETFS:
                resp = self._fmp.get_historical_prices(symbol, days=60)
                rotation_histories[symbol] = _extract_history(resp, symbol)

            # Compute 6 top-risk sub-components
            dist_days = _top_risk_distribution_days(spy_history, spy_history)  # use SPY twice (no QQQ separate fetch)
            index_tech = _top_risk_index_technical(spy_history)
            leading = _top_risk_leading_stocks(spy_history, iwm_history)
            defensive = _top_risk_defensive_rotation(rotation_histories)
            breadth = _top_risk_breadth_divergence(spy_history)
            sentiment = _top_risk_sentiment(spy_history)

            component_results = {
                "distribution_days":  dist_days,
                "index_technical":    index_tech,
                "leading_stocks":     leading,
                "defensive_rotation": defensive,
                "breadth_divergence": breadth,
                "sentiment":          sentiment,
            }

            composite = _top_risk_composite_score(component_results)
            risk_zone = _score_to_zone(composite)

            # Update cache
            self._cached_top_risk = composite
            self._cached_risk_zone = risk_zone
            self._top_risk_cached_at = datetime.utcnow()
            self._cached_components.update({
                "top_risk": {
                    k: {"score": v.get("score", 0), "data_available": v.get("data_available", False)}
                    for k, v in component_results.items()
                },
                "top_risk_composite": composite,
            })
            logger.info(
                "Macro regime: {} (confidence={:.2f}, top_risk={:.0f}, zone={})",
                self._cached_regime, self._cached_regime_confidence, composite, risk_zone,
            )
        except Exception as exc:
            logger.warning("Top-risk refresh failed: {} — using cached/default values", exc)
