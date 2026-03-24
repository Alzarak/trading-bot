"""Exposure gating for the trading bot pipeline.

Synthesizes a RegimeState into an ExposureDecision that governs:
  - Maximum portfolio exposure percentage
  - Whether new BUY entries are permitted (bias)
  - Position size scaling factor

Gating rules (D-06, configurable via config.pipeline.regime_gating — D-07):
  - top_risk >= 70: SELL_ONLY mode, no new entries (EXP-02)
  - regime == contraction: position_size_multiplier = 0.5 (EXP-03)
  - top_risk 41-69: linear size reduction from 1.0 to 0.5 (D-08)
  - current_exposure >= ceiling: SELL_ONLY (EXP-04)
"""
from __future__ import annotations

from loguru import logger

from scripts.models import ExposureDecision, RegimeState

# Regime score mapping: higher = more bullish regime
# Adapted from exposure-coach REGIME_SCORES dict
REGIME_SCORES: dict[str, int] = {
    "broadening": 80,
    "concentration": 60,
    "transitional": 50,
    "inflationary": 40,
    "contraction": 20,
}


def _determine_exposure_ceiling(regime_score: int) -> float:
    """Map regime score to maximum portfolio exposure percentage.

    Non-linear mapping adapted from exposure-coach calculate_exposure.py.
    Higher regime score = more permissive exposure ceiling.
    """
    if regime_score >= 70:
        return 95.0
    elif regime_score >= 50:
        return 80.0
    elif regime_score >= 30:
        return 60.0
    else:
        return 40.0


def _determine_bias(regime_score: int) -> str:
    """Map regime score to exposure bias.

    Returns bot-specific literals (NOT the reference's "GROWTH"/"VALUE"/etc).
    """
    if regime_score >= 70:
        return "risk_on"
    elif regime_score >= 40:
        return "neutral"
    else:
        return "risk_off"


class ExposureCoach:
    """Synthesizes RegimeState into ExposureDecision.

    Instantiated with config dict. The config is read once at init so
    thresholds are not re-parsed on every evaluate() call.

    Args:
        config: Bot config dict (config.json loaded as dict).
                Reads from config["pipeline"]["regime_gating"] for thresholds.
    """

    def __init__(self, config: dict) -> None:
        gating = config.get("pipeline", {}).get("regime_gating", {})
        # D-07: all thresholds configurable — sensible defaults match D-06 spec
        self._block_buys_above: float = float(
            gating.get("block_buys_top_risk_above", 70)
        )
        self._contraction_pct: float = float(
            gating.get("reduce_size_contraction_pct", 50)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self, regime: RegimeState, current_exposure_pct: float
    ) -> ExposureDecision:
        """Synthesize regime state into an exposure decision.

        Args:
            regime: Current RegimeState from RegimeDetector.detect().
            current_exposure_pct: Current portfolio exposure 0-100.

        Returns:
            ExposureDecision with max_exposure_pct, bias, position_size_multiplier.
        """
        # EXP-02: block BUYs when top_risk >= threshold (D-06)
        if regime.top_risk_score >= self._block_buys_above:
            decision = ExposureDecision(
                max_exposure_pct=current_exposure_pct,  # no new entries
                bias="SELL_ONLY",
                position_size_multiplier=0.0,
                reason=(
                    f"top_risk={regime.top_risk_score:.0f} >= {self._block_buys_above:.0f} "
                    f"(zone={regime.risk_zone})"
                ),
            )
            logger.info(
                "ExposureCoach: SELL_ONLY — top_risk={:.0f} >= {:.0f}",
                regime.top_risk_score,
                self._block_buys_above,
            )
            return decision

        regime_score = REGIME_SCORES.get(regime.regime, 50)
        max_exp = _determine_exposure_ceiling(regime_score)
        bias = _determine_bias(regime_score)

        # EXP-04: block new entries when current exposure meets or exceeds ceiling
        if current_exposure_pct >= max_exp:
            decision = ExposureDecision(
                max_exposure_pct=max_exp,
                bias="SELL_ONLY",
                position_size_multiplier=0.0,
                reason=(
                    f"exposure_ceiling={max_exp:.0f}% reached "
                    f"(current={current_exposure_pct:.0f}%)"
                ),
            )
            logger.info(
                "ExposureCoach: SELL_ONLY — exposure ceiling {:.0f}% reached "
                "(current={:.0f}%)",
                max_exp,
                current_exposure_pct,
            )
            return decision

        # EXP-03: contraction regime halves position size (D-06)
        size_mult = 1.0
        if regime.regime == "contraction":
            size_mult = (100.0 - self._contraction_pct) / 100.0  # 0.5 default
        # D-08: linear size reduction in top_risk 41-69
        elif 41 <= regime.top_risk_score < self._block_buys_above:
            ratio = (regime.top_risk_score - 41.0) / (self._block_buys_above - 41.0)
            size_mult = 1.0 - (0.5 * ratio)  # 1.0 at 41, 0.5 at threshold

        decision = ExposureDecision(
            max_exposure_pct=max_exp,
            bias=bias,
            position_size_multiplier=round(size_mult, 4),
            reason=(
                f"regime={regime.regime} score={regime_score} "
                f"top_risk={regime.top_risk_score:.0f} zone={regime.risk_zone}"
            ),
        )
        logger.info(
            "ExposureCoach: {} — max={:.0f}% size_mult={:.2f} "
            "(regime={} top_risk={:.0f})",
            bias,
            max_exp,
            size_mult,
            regime.regime,
            regime.top_risk_score,
        )
        return decision
