"""Pipeline modules for the regime-gated, conviction-scored signal pipeline.

Phase 1 modules:
    fmp_client  — Shared FMP API client with graceful degradation
    regime      — Macro regime detection + market top risk scoring
    exposure    — Exposure gating (ExposureCoach → ExposureDecision)

Phase 2 modules (added in Phase 2):
    screeners   — Technical, earnings drift, VCP signal generation
    aggregator  — Weighted conviction aggregation across screeners
    sizer       — ATR-based and Kelly position sizing

Phase 3 modules (added in Phase 3):
    analyzer    — Regime-aware Claude analysis prompts
    thesis_manager  — IDEA→ACTIVE→CLOSED thesis lifecycle in SQLite
    postmortem  — Outcome tracking and screener weight feedback
"""
