# Alien Recommendation Card: Default Sparse Export Absent Weight

Bead: `br-r37-c1-04z53.1`

Target: default `adjacency_matrix`, `to_scipy_sparse_array`, and Laplacian sparse exports on simple `Graph`/`DiGraph` inputs where `weight="weight"`, `dtype=None`, and no edge carries `weight`.

Profile: `profile_to_scipy_default_before.txt` shows five `to_scipy_sparse_array` calls spending 3.006 s cumulative, dominated by Python adjacency-view materialization. The deterministic BA(8000,4) sweep shows `to_scipy_default` fnx mean 0.386670578 s vs NetworkX mean 0.030083685 s with matching digest `987fb0c41578a61146699304815a73d3c6d70160384e8fb3046d1d0c7b7d13c6`.

Primitive: contiguous native COO emission with zero per-edge Python boundary crossings. This matches the alien-graveyard optimization contract: baseline, profile, golden proof, one lever, verify, and reprofile. The applied implementation is a safe-Rust edge-attribute presence scan followed by the existing native unit-weight COO builder only when the requested attribute is absent.

Expected value: Impact 5 x Confidence 5 / Effort 2 = 12.5. This is above the EV >= 2.0 keep threshold because the target is a 12.85x residual vs-upstream gap and the fallback preserves all weighted dtype semantics.

Proof obligations:
- Ordering: `nodelist` order is unchanged; SciPy COO to CSR canonicalization produces the same row/column set and digest.
- Tie-breaking: none on this matrix construction path.
- Floating point: absent-weight fast path emits unit weights and preserves integer dtype inference; weighted float/int attrs remain on the old Python fallback when `dtype=None`.
- RNG: benchmark graph construction uses a fixed BA seed; library path does not use RNG.
- Error behavior: empty graph, duplicate/missing `nodelist`, multigraphs, subclasses, and non-string weights keep existing checks and fallbacks.

Fallback: if `_native_has_edge_attr` is unavailable, returns `None`, sees any requested attr, or the graph is a multigraph/non-fnx shape, use the existing Python fallback. This fallback is required to preserve NetworkX value-type dtype inference for attrs such as `2.0`.
