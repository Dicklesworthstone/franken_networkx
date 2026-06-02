# Change 001: Native COO for Absent Default Weight

Bead: `br-r37-c1-04z53.1`

## Target

Default sparse exports on simple fnx `Graph`/`DiGraph` inputs where callers pass NetworkX defaults: `weight="weight"`, `dtype=None`, and no edge carries a `weight` attribute.

## Baseline

Profile artifact: `profile_to_scipy_default_before.txt`.

Five `to_scipy_sparse_array` calls spent 3.006 s cumulative. The profile was dominated by Python adjacency-view materialization (`_atlas` and `__getitem__`), not by SciPy sparse construction.

Focused rch sampled benchmark, BA(8000,4), `to_scipy_default`:

- Before: 0.403971429876 s mean, digest `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.
- NetworkX: 0.043191539378 s mean, same digest.

## Lever

Expose `graph_has_edge_attr` from the PyO3 layer for simple graphs. In Python, when `weight` is a string and `dtype is None`, call that native scan. If it proves the attribute is absent, route through `_native_adjacency_arrays(G, nodelist, None, 1.0)`.

Any present attribute, multigraph, non-fnx graph, unavailable helper, or unsupported shape stays on the existing Python fallback.

## Isomorphism Proof

- Ordering: `nodelist` order is unchanged. Native COO emits the same coordinate set as the Python adjacency walk, and SciPy COO-to-CSR canonicalization preserves the observable CSR bytes.
- Tie-breaking: not applicable; matrix export has no tie-break decision.
- Floating point: absent default weights are unit weights. The existing integer-dtype inference remains in the native path. Present attrs, including `2.0` values that must infer float under `dtype=None`, stay on the Python fallback.
- RNG: no library RNG is used. The benchmark graph seed is fixed.
- Error behavior: empty graph, empty/duplicate/missing nodelist, multigraphs, subclasses, non-string weights, and present attrs retain existing checks/fallbacks.

## After

Focused rch sampled benchmark, same workload:

- After: 0.046158666501 s mean, digest `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.
- Delta: 88.57% faster, 8.7518x speedup.

After sweep:

- `adjacency_default`: 0.427744767333 s -> 0.061860712798 s, 6.9146x faster, digest matched.
- `to_scipy_default`: 0.386670577670 s -> 0.041040136595 s, 9.4218x faster, digest matched.
- `laplacian_default`: 0.400101954331 s -> 0.040028750998 s, 9.9954x faster, digest matched.
- `normalized_laplacian_default`: 0.392258193664 s -> 0.039663495403 s, 9.8897x faster, digest matched.

Post-change profile: `profile_to_scipy_default_after.txt`. Python adjacency materialization is gone from the top path; `_fnx.adjacency_arrays` is 0.136 s for five calls and `_fnx.graph_has_edge_attr` is 0.019 s.

## Decision

Score: Impact 5 x Confidence 5 / Effort 2 = 12.5. Keep.
