# br-r37-c1-04z53.72 report

## Target

Fresh reduced benchmark on current `main` found `degree_centrality_5k` as the
only live regression in the standard matrix:

- genuine NetworkX p50: `0.652ms`
- FNX p50: `1.433ms`
- ratio: `2.20x` slower

Formal bead baseline used BA(5000, 5), copied from NetworkX into FNX once per
process, then ran 300 `degree_centrality` calls.

## Lever

For simple `Graph`, `_fnx.degree_centrality` now fills the Python result dict
directly from integer node order using `Graph::degree_by_index`.

This removes the intermediate `Vec<CentralityScore>` and 5,000 owned canonical
node strings per call. Directed and multigraph paths still use the existing
centrality result conversion.

## Evidence

RCH-wrapped hyperfine, 15 runs, 300 calls per process:

- FNX: `634.910ms +/- 29.354ms -> 481.876ms +/- 20.365ms` (`1.32x` self)
- NetworkX context: `539.669ms +/- 34.259ms -> 578.191ms +/- 24.989ms`
- vs NetworkX: FNX moved from `1.18x` slower to `1.20x` faster

cProfile over 300 FNX calls:

- `_fnx.degree_centrality`: `0.307s -> 0.101s`
- total profile time: `0.309s -> 0.103s`

## Proof

Golden proof SHA stayed unchanged:

- `1710593c67cd647d3a01b25e8447ec9136abc11e01ce43c278e2a9f1ff43e18d`

Cases:

- empty graph
- singleton
- path graph
- self-loop graph
- BA(5000, 5)

All FNX canonical result hashes match NetworkX exactly.

Isomorphism:

- ordering: both emit nodes in graph insertion order
- tie-breaking: none; degree centrality is per-node arithmetic
- floating point: both use `degree * (1.0 / (n - 1))`; exact string hashes checked
- RNG: only deterministic BA fixture construction with `seed=42`

## Gates

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed on `vmi1227854` with known `fnx-generators` warnings
- `maturin develop --release --features pyo3/abi3-py310`: passed with known `fnx-generators` warnings
- focused pytest: `66 passed`
- `py_compile` harness: passed
- `cargo fmt -p fnx-python --check`: blocked by pre-existing formatting drift outside this helper
- clippy strict: blocked by pre-existing `collapsible_if` in `digraph.rs`/`lib.rs`
- clippy with that known lint allowed: passed on `vmi1227854`

## Verdict

Kept. Score `5.3` (`Impact 4 * Confidence 4 / Effort 3`).

Next target: rerun the benchmark matrix after push. If no ready perf child is
filed, route to the next measured vs-NetworkX regression rather than extending
degree centrality.
