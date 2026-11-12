# Risk Note — Track E: Performance, Durability, Fuzz, CI Gates

## Risk Surface
- parser/ingestion: E6 fuzz harnesses may discover crash bugs in parsers → those become P0 fixes
- algorithmic denial vectors: restored SLO budgets (E1) may be genuinely unachievable for certain graph classes → performance gate blocks merges
- **CI run time**: G1-G8 sequential pipeline may become too slow for developer iteration

## Failure Modes
- fail-closed triggers: SLO restoration (E1) causes perf gate to fail on every PR until algorithms are optimized → developer friction
- degraded-mode triggers: fuzz corpus grows unboundedly → repo bloat

## Mitigations
- controls: E1 allows per-row downgrade with documented rationale; E3 profile-and-prove loop ensures optimizations carry correctness proof; fuzz corpus size gated by gitignore patterns
- tests: E4 perf gate runs in CI with artifact upload; E9 decode-drill exercises RaptorQ recovery on every CI run

## Residual Risk
- unresolved risks: flamegraph SVGs (E3.1) may add repo bloat even when gzip-compressed; may need to store in a separate artifact bucket
- follow-up actions: monitor CI pipeline duration; if > 30 min, add parallelism between independent gates
