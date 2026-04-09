# Risk Note — Track D: Strict/Hardened Mode Wiring

## Risk Surface
- parser/ingestion: D3 adds fail-closed behavior to parsers on unknown metadata; incorrect fail-closed triggers could reject valid graphs
- algorithmic denial vectors: hardened-mode Bayesian admission controller adds per-parse overhead; adversarial inputs designed to maximize posterior updates could slow parsing

## Failure Modes
- fail-closed triggers: strict mode rejects a valid GraphML/GML file due to an unexpected but benign XML attribute → user perceives breakage
- degraded-mode triggers: hardened mode recovers from a genuinely malformed input but the recovery path produces a subtly different graph than NX would → silent semantic drift

## Mitigations
- controls: D3 24 strict fixtures + D4 24 hardened fixtures; decision ledger (D7) enables forensic audit of every mode-mediated decision; drift ledger feedback (D8) auto-creates beads for under-confident decisions
- tests: strict fixtures prove fail-closed on all malformed inputs across 4 formats; hardened fixtures prove bounded recovery with audit trail

## Residual Risk
- unresolved risks: the loss matrix (D5) is empirically thin with only ~48 fixtures — Bayesian shrinkage mitigates but doesn't eliminate noisy estimates; real-world parser inputs may have very different characteristics than the fixture corpus
- follow-up actions: expand adversarial fixture corpus after initial deployment; monitor decision ledger confidence distribution in real usage
