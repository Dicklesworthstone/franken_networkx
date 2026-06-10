# perf(weakly_connected_components): integer-CSR BFS

br-r37-c1-uiq2y

## Problem
The `weakly_connected_components` native kernel (fnx-algorithms) walked the
undirected projection with a **String-keyed `HashSet<&str>`** visited set over
`successors_iter`/`predecessors_iter` (per-node String hashing), then
`sort_unstable()`d **every component** AND the **whole component list**
(lexicographic by node name). Result: **~15× slower than nx** at 100k edges
(n=1500 gnp directed: 5.21 ms vs nx 0.35 ms) — even though nx's is pure Python.

The `number_weakly_connected_components` sibling already used an integer-CSR
BFS; the listing variant never got the same treatment.

## Lever (one)
Integer-CSR BFS over the undirected projection: `successors_indices(u) ∪
predecessors_indices(u)` with a `Vec<bool>` visited array (no String hashing),
node names materialised **once** at the end (`names[i].to_owned()`). Components
are emitted in **NetworkX discovery order** — outer scan over node index
`0..n`, one component per first-unvisited node — matching nx's `for v in G`
generation exactly. The two `sort_unstable()` calls are deleted: the Python
wrapper wraps each component in `set(...)` (intra-component order irrelevant)
and the nx contract yields components in discovery order, not sorted order.

Touched: `crates/fnx-algorithms/src/lib.rs` (`weakly_connected_components`).

## Proof (nx-exact)
`harness_proof.py`: 11 cases — gnp directed ×6 seeds, multi-component+isolated,
string labels+self-loops, MultiDiGraph, empty, single node. **0 set-content
mismatches AND 0 discovery-order mismatches vs nx** (the new output matches nx
both as a set-of-frozensets and as an ordered list-of-sets).
Golden sha256 (discovery-order-preserving, sorted-within fingerprint; identical
to nx): `a9fc0e1c395579c0cd1f1aedae8b847bff921098fe0fe0f1c0b651159ec3eecb`

pytest -k "weakly/connected_component": **351 passed, 6 skipped**.

## Timing (warm min-of-9, gnp_random_graph(n, p, directed))
| n    | E       | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|---------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 1500 | 112,265 |   5.209 ms   | 0.348 ms |    14.97×      | 0.346 ms |   0.99×   |   **15.1×**  |
| 3000 |  89,817 |   6.402 ms   | 1.216 ms |     5.27×      | 0.596 ms | **0.50×** |    10.7×     |
| 5000 |  99,985 |   9.407 ms   | 1.893 ms |     4.97×      | 1.712 ms |   0.89×   |     5.5×     |

~15× slower → parity-to-2×-faster (5.5–15.1× self-speedup).

## Score
Impact: high (15× gap eliminated on a core directed-connectivity primitive;
now ≤ nx). Confidence: high (byte-identical golden sha incl. discovery order,
0/11 vs nx across MultiDi/self-loop/string/isolated, 351 tests). Effort: low
(one kernel, mirrors the existing `number_` sibling). Score ≫ 2.0.
