# Risk Note — Track C: CGSE Crown Jewel Realization

## Risk Surface
- parser/ingestion: N/A (CGSE does not modify parsers)
- algorithmic denial vectors: witness emission adds per-decision overhead to every CGSE-instrumented algorithm; adversarial graphs with maximum tie-break opportunities could cause witness ledger bloat
- **compile-time explosion**: const-generic TieBreakPolicy × 12 algorithms could cause monomorphization blowup; measured in C2.1

## Failure Modes
- fail-closed triggers: algorithm produces different ordering than NX oracle after CGSE wiring → conformance gate fails
- degraded-mode triggers: witness ledger exceeds memory budget on very large graphs → ring buffer overflow; mitigated by fixed-size thread-local buffer

## Mitigations
- controls: C5 adversarial tie-break corpus with 600+ graphs; C6 counter-example mining loop; existing 1394-test parity suite remains the primary correctness gate
- tests: 8 CGSE unit tests (policy serde roundtrip, witness hash determinism, ledger JSONL, thread-local ledger); C4 wiring tests per algorithm; C5 adversarial fixtures

## Residual Risk
- unresolved risks: CGSE policies are *declared*, not *enforced* — an algorithm that ignores its declared policy and orders differently will only be caught by the adversarial corpus, not at compile time. Type-level enforcement (C2.1) may not be feasible without significant compile-time cost.
- follow-up actions: measure compile-time delta after C4 wiring; if > 20%, switch to runtime dispatch with cfg(test) compile-time check
