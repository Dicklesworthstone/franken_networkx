# perf(node_boundary): integer-CSR scan

br-r37-c1-crb49

## Problem
The `node_boundary` native kernel (fnx-algorithms) called `graph.neighbors(node)`
for every node in `nbunch` — which **allocates a `Vec<&str>` of neighbour names**
per node — tested membership against a `HashSet<&str>` (per-name String hashing),
and collected the boundary into a **`BTreeMap<&str,()>`** (sorted output). The
Python wrapper wraps the result in `set(...)` (nx returns a set), so the BTreeMap
ordering was wasted work. Result: **3.2× slower at |S|=300, growing to 4.6× at
|S|=2400** — the per-node Vec allocation + String hashing scales with the scan.

## Lever (one)
Integer-CSR scan: resolve `nbunch` (and `nbunch2`) to node **indices** once via
`get_node_index`, walk `neighbors_indices(u)` (`&[usize]`, zero allocation), gate
"in nbunch" / "in nbunch2" membership with `Vec<bool>` stamp arrays, dedup the
boundary with another stamp array, and materialise node names **once** at the
end. The `BTreeMap` sort is dropped (the `set()` wrapper makes order
irrelevant). Same String-keyed → integer-CSR lever family as
`weakly_connected_components` / `node_connected_component`.

Touched: `crates/fnx-algorithms/src/lib.rs` (`node_boundary`).

## Proof (nx-exact)
`harness_proof.py`: 19 cases — gnp ×6 seeds with/without `nbunch2`, disconnected
graph, isolated node, string labels + self-loop, empty S, **duplicate nodes in
S**, S = all nodes. **0 mismatches vs nx** (full set equality); result
`isinstance set` preserved.
Golden sha256 (sorted boundary fingerprint, identical to nx):
`7139f5959546b1e4b26c03ac71a662aebb7f318f71f61ec5ab7434832b87f863`

pytest -k "boundary/expansion/cut_size/volume": **186 passed**.

## Timing (warm min-of-9, gnp_random_graph(n, 0.005), |S| growing)
| n    | \|S\| | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|------:|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 3000 |   300 |   0.645 ms   | 0.204 ms |     3.16×      | 0.258 ms |   1.08×   |    2.5×      |
| 5000 |  1000 |   2.950 ms   | 0.872 ms |     3.38×      | 0.531 ms | **0.72×** |    5.6×      |
| 8000 |  2400 |  10.615 ms   | 2.310 ms |     4.60×      | 1.007 ms | **0.46×** |   10.5×      |

3.2–4.6× slower (growing) → parity-to-2×-faster (2.5–10.5× self-speedup).

## Score
Impact: high (size-growing 3.2–4.6× gap eliminated on a boundary primitive used
by node_expansion/cut_size; now ≤ nx). Confidence: high (byte-identical golden
sha, 0/19 vs nx incl. nbunch2/dup-S/self-loop/disconnected, 186 tests). Effort:
low (one kernel, proven lever). Score ≫ 2.0.
