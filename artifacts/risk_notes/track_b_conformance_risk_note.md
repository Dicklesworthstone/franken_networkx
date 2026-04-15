# Risk Note — Track B: Conformance and Evidence Restoration

## Risk Surface
- parser/ingestion: regenerated fixtures and replay bundles may silently normalize malformed inputs differently from the canonical pytest contract
- algorithmic denial vectors: differential fuzzing and metamorphic/property suites can surface real hostile-graph regressions that immediately turn into release blockers
- **source-of-truth drift**: keeping pytest and `fnx-conformance` aligned is itself a compatibility risk
- **provenance contamination**: stale fixture bundles or hand-edited evidence artifacts can make parity claims look fresher than they are

## Failure Modes
- fail-closed triggers: freshness gate marks evidence stale after algorithm or binding changes, blocking merges until the conformance bundle is regenerated
- degraded-mode triggers: nightly differential/metamorphic suites produce a large quarantine queue of flaky or under-triaged divergences

## Mitigations
- controls: B1 declares pytest as the canonical observable-behavior oracle; B3/B4 require durability sidecars and freshness gates; B8 keeps a provenance-linked historical regression corpus
- tests: canonical `pytest tests/python/ -v --tb=long`; curated `fnx-conformance` smoke/replay runs; differential fuzzing plus metamorphic/property suites

## Residual Risk
- unresolved risks: machine-generated evidence can still be misleading if the oracle fixture itself is wrong or underspecified in an ambiguity zone
- follow-up actions: keep divergence triage deterministic, attach minimized repro fixtures to every new regression, and prefer fixing fixture provenance over weakening parity claims
