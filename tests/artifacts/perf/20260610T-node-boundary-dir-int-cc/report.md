# perf(node_boundary_directed): integer-CSR scan

br-r37-c1-ij4ly

## Problem
The directed `node_boundary` kernel (`node_boundary_directed`, used for DiGraph /
MultiDiGraph) mirrored the same anti-pattern fixed in the undirected sibling
(br-r37-c1-crb49): `graph.successors(node)` **allocates a `Vec<&str>` of
successor names** per nbunch node, membership tested via `HashSet<&str>` (per-name
String hashing), boundary collected into a **`BTreeMap`** (sorted output). The
Python wrapper wraps the result in `set(...)`, so the sort is wasted. Result:
**2.3× slower at |S|=600, growing to 5.0× at |S|=2400**.

## Lever (one)
Integer-CSR scan: resolve `nbunch`/`nbunch2` to node **indices** once via
`get_node_index`, walk `successors_indices(u)` (`&[usize]`, zero allocation),
gate membership with `Vec<bool>` stamp arrays, dedup the boundary with a stamp
array, materialise node names **once** at the end; drop the `BTreeMap` sort.

Touched: `crates/fnx-algorithms/src/lib.rs` (`node_boundary_directed`).

## Proof (nx-exact)
`harness_proof.py`: 20 cases — gnp directed ×6 seeds ± `nbunch2`, disconnected,
isolated, string labels + self-loop, empty/duplicate/all-S, **MultiDiGraph**.
**0 mismatches vs nx** (full set equality); result `isinstance set` preserved.
Golden sha256 (sorted boundary fingerprint, identical to nx):
`c6d0df5642e2c3b25453572e5e68111729253a6a177f575d590599c47067b984`

pytest -k "boundary/expansion/cut_size": **170 passed**.

## Timing (warm min-of-9, gnp_random_graph(n, 0.004, directed), |S| growing)
| n    | \|S\| | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|------:|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 2500 |   600 |   0.733 ms   | 0.321 ms |     2.28×      | 0.183 ms | **0.57×** |    4.0×      |
| 5000 |  1000 |   2.835 ms   | 0.799 ms |     3.55×      | 0.446 ms | **0.69×** |    6.4×      |
| 8000 |  2400 |   9.898 ms   | 1.982 ms |     4.99×      | 0.890 ms | **0.46×** |   11.1×      |

2.3–5.0× slower (growing) → faster than nx at every size (4.0–11.1× self-speedup).

## Score
Impact: high (size-growing 2.3–5.0× gap eliminated on the directed boundary
primitive; now < nx). Confidence: high (byte-identical golden sha, 0/20 vs nx
incl. MultiDiGraph/nbunch2/self-loop/dup-S, 170 tests). Effort: low (one kernel,
proven lever). Score ≫ 2.0.
