# Risk Note — Track G: Crown-Jewel Multipliers

## Risk Surface
- parser/ingestion: indirect exposure only; most Track G work changes analysis and prioritization layers rather than ingestion code
- algorithmic denial vectors: advanced selection, tail-modeling, and corpus-dedup logic can hide or mis-rank real hostile-graph regressions if the math is miscalibrated
- **model-calibration risk**: conformal bands, Bayesian tail estimates, and novelty scoring can become false-confidence generators if fitted on weak or biased history
- **auditability risk**: compressed summaries and research-grade heuristics can obscure the simple factual question of whether parity or performance regressed

## Failure Modes
- fail-closed triggers: a statistical gate rejects safe changes because the historical model is underfit, stale, or operating out of regime
- degraded-mode triggers: optional Track G machinery runs in shadow mode and produces noisy or contradictory prioritization signals that developers stop trusting

## Mitigations
- controls: keep Track G optional and downstream of proven A-F evidence; require shadow-mode validation before any statistical model becomes release-blocking; retain raw artifacts beside compressed summaries and scored recommendations
- tests: backtest every predictive gate on historical benchmark/conformance runs; require calibration reports for conformal and Bayesian models; keep deterministic fallbacks for triage and replay

## Residual Risk
- unresolved risks: research-grade methods add maintenance burden and can exceed the team's validation bandwidth
- follow-up actions: land Track G incrementally, publish calibration/error reports with each model, and prefer interpretable failure envelopes over clever but opaque gating logic
