# perf(node_connected_component): integer-CSR BFS

br-r37-c1-eevod

## Problem
The `node_connected_component` native kernel (fnx-algorithms) walked the
component with a **String-keyed `HashSet<&str>`** visited set over
`neighbors_iter` (per-node String hashing), then `sort_unstable()`d the
resulting node names. The Python wrapper wraps the result in `set(...)` (nx
returns a set), so the sort is pure waste. Result: **3.4× slower at n=3000,
growing to 10× at n=10000** — the String-hashing tax scales with component
size.

## Lever (one)
Integer-CSR BFS: resolve the start node once via `get_node_index`, traverse
with `neighbors_indices(u)` and a `Vec<bool>` visited array (no String
hashing), materialise node names **once** at the end. Drop `sort_unstable()`
(the `set(...)` wrapper makes intra-component order irrelevant). This is the
same String-keyed-BFS → integer-CSR lever that took
`weakly_connected_components` 15×→parity (br-r37-c1-uiq2y).

Touched: `crates/fnx-algorithms/src/lib.rs` (`node_connected_component`).

## Proof (nx-exact)
`harness_proof.py`: 32 cases — gnp ×6 seeds × 4 source nodes, disconnected
graph (clusters + isolated nodes), string labels + self-loop. **0 mismatches
vs nx** (full set equality); result `isinstance set` preserved.
Golden sha256 (sorted component fingerprint, identical to nx):
`5a3bdf4a9b10dc86c280339ff1f5bfa1f12052f9b816bc54cef2a0e0bbf4f8bf`

pytest -k "node_connected/connected_component/connectivity": **665 passed,
6 skipped**.

## Timing (warm min-of-9, gnp_random_graph(n, 0.01))
| n     | E       | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|-------|---------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 3000  |  45,249 |   2.727 ms   | 0.799 ms |     3.41×      | 0.531 ms | **0.67×** |    5.1×      |
| 6000  | 179,969 |  12.815 ms   | 1.784 ms |     7.18×      | 1.246 ms | **0.72×** |   10.3×      |
| 10000 | 499,886 |  37.512 ms   | 3.717 ms |    10.09×      | 3.589 ms | **0.85×** |   10.5×      |

3.4–10× slower (growing) → faster than nx at every size (5.1–10.5× self-speedup).

## Score
Impact: high (size-growing 3.4–10× gap eliminated on a core connectivity query;
now < nx). Confidence: high (byte-identical golden sha, 0/32 vs nx incl.
disconnected/string/self-loop, 665 tests). Effort: low (one kernel, proven
lever). Score ≫ 2.0.
