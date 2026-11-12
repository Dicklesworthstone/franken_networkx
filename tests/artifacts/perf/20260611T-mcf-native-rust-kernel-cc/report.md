# perf: native safe-Rust integer network-simplex kernel — min_cost_flow BEATS nx

Bead: br-r37-c1-8foqi. After the Python port (d1abfbbc5), min_cost_flow was ~1.25x slower
than nx; the only Python-bound remainder was the spanning-tree PIVOT loop (its array ops
run at nx's speed). This builds the directive's own native safe-Rust kernel.

## Lever (ONE)
New `crates/fnx-python/src/network_simplex.rs`: a faithful transcription of NetworkX's
primal network-simplex pivot logic (BSD), specialised to i64 demands/capacities/weights.
NetworkX encodes the dummy root via Python's negative-index `-1` alias for index `n`;
the Rust kernel makes the root the explicit index `n` and uses `usize::MAX` for a true
None parent. The Python `network_simplex` extracts the flat integer arrays (via the
_FastG native bulk read) and calls the kernel for all-integer inputs; float / huge-
magnitude inputs keep the verbatim Python pivots. Flow-dict construction unchanged.

## Proof (cost-exact)
- 200-trial random corpus (n=4..40, neg weights, inf caps, infeasible+unbounded cases):
  kernel cost == nx for all 163 feasible; status correct for all 37 infeasible/unbounded.
- min_cost_flow golden e335234e unchanged (cost==nx, flow balance==nx, valid optimum).
- 22252 tests pass (full suite, not-slow); 1072 flow/min_cost/network_simplex/capacity_
  scaling/error_message tests pass. clippy-clean, fmt-clean.

## Benchmark (gnp directed, real demands, interleaved)
| n    | nx (ms) | fnx (ms) | ratio       |
|------|---------|----------|-------------|
| 300  | 11.1    | 7.3      | 0.65x (1.5x faster) |
| 600  | 37.5    | 18.8     | 0.50x (2.0x faster) |
| 1500 | 120.7 (ns) | kernel+extract 23.5 | 0.19x (5x faster, solver) |

min_cost_flow journey: SSP 50-96x slower -> Python port 1.25x -> native kernel 0.5-0.65x
(1.5-2x FASTER than nx). The kernel-only solve is ~25x faster than nx's Python pivots.
Integer fast path; float inputs keep the byte-exact Python pivots.
