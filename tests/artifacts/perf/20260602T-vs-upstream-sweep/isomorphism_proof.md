# br-r37-c1-04z53.1 Isomorphism Proof

## Target

- Workload: default `adjacency_matrix(G)` / `to_scipy_sparse_array(G)` on deterministic BA(8000,4), 31,984 edges.
- Profile-backed hotspot: Python adjacency-view materialization in `to_scipy_sparse_array`.
- Alien primitive: native contiguous COO emission instead of per-edge Python/PyO3 view traversal.

## One Lever

Add `graph_has_edge_attr(G, weight)` over live Python `edge_py_attrs`, then route only this case to native unit-weight COO:

- `weight` is a string.
- `dtype is None`.
- graph is simple fnx `Graph`/`DiGraph`.
- no edge has the requested weight attr.

Any present attr, multigraph, subclass, or unavailable native helper keeps the existing Python fallback.

## Before / After

Hyperfine command artifact: `baseline_adjacency_default_hyperfine.json` -> `after_adjacency_default_hyperfine.json`.

- fnx before: 3.710682909 s mean.
- fnx after: 0.914357362 s mean.
- speedup: 4.06x, 75.36% faster.
- upstream nx after: 0.845362410 s mean.
- remaining gap: about 1.08x.

## Golden Output

Matrix SHA-256 digest matched baseline fnx, after fnx, and upstream nx:

`987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`

Verified consumers in `after_sweep_n8000.jsonl`:

- `adjacency_default`: digest matched.
- `to_scipy_default`: digest matched.
- `laplacian_default`: digest matched.
- `normalized_laplacian_default`: digest matched.

## Isomorphism

- Ordering preserved: yes. `nodelist` order is unchanged; native edge iteration emits the same coordinate set, and SciPy canonicalizes the sparse output.
- Tie-breaking unchanged: N/A. Sparse matrix export has no tie-breaking branch.
- Floating-point unchanged: N/A for this route. Unit edge values still pass through existing dtype inference and produce integer output.
- RNG unchanged: benchmark graph seed is deterministic; library code does not use RNG.
- Error behavior unchanged: empty graph, empty nodelist, duplicate nodelist, missing nodelist nodes, multigraphs, subclasses, and present weight attrs stay on existing branches.

## Post-Change Profile

Artifact: `after_profile_adjacency_default_fnx.txt`.

The `_atlas` / `__getitem__` Python adjacency-view hotspot is gone. `_fnx.adjacency_arrays` is now the measured matrix-export work at 0.080 s for 3 calls.
