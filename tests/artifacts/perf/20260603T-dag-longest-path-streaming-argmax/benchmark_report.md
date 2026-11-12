# br-r37-c1-obbmt: dag_longest_path streaming stable argmax

## Target

- Bead: `br-r37-c1-obbmt`
- Fixture: deterministic 400-node DiGraph DAG, edge probability `0.02`, seed `20260603`
- Operation: `dag_longest_path(G)` only
- Profile-backed hotspot: after bulk predecessor snapshots, `_dag_longest_path_digraph_native` still spent `0.040s / 120` in `max` and `0.009s / 120` in the per-node lambda/list path.

## Baseline

- FNX direct rch timing: `0.3796768040047027s / 300` = `0.0012655893466823425s` per call
- NetworkX oracle rch timing: `0.30437323098885827s / 300` = `0.0010145774366295275s` per call
- Baseline cProfile: `0.24168067899881862s / 120`
- Hyperfine baseline via rch, 120 repeats: `453.5 ms +/- 17.9 ms`
- Golden SHA: `76214d0b33d25b721eb1437d081b03fcf320e749ed72ceb521a87215d5ebbb7f`

## Change

Replace per-node candidate-list allocation plus `max(us, key=lambda x: x[0])` with a streaming stable argmax accumulator. The accumulator initializes from the first predecessor and updates only when a later candidate is strictly greater.

## After

- FNX direct rch timing: `0.3482393389858771s / 300` = `0.0011607977966195905s` per call
- Direct self-speedup: `1.09x`
- cProfile: `0.20199158298783004s / 120` (`1.20x`)
- Hyperfine via rch: `437.2 ms +/- 26.2 ms` (`1.04x`)
- Golden SHA: `76214d0b33d25b721eb1437d081b03fcf320e749ed72ceb521a87215d5ebbb7f`
- Score: Impact `1.09` x Confidence `3` / Effort `1` = `3.27`; keep.

