# weighted sparse default-order native COO proof

Bead: `br-r37-c1-0o6ad`

Target: `fnx.to_scipy_sparse_array(Graph, dtype=float, weight="weight")` on deterministic BA(8000,4,seed=12345), default `nodelist=None`, `format="csr"`.

Profile-backed hotspot:
- Baseline profile: `profile_to_scipy_weighted_float_fnx.txt`; five calls spent 0.141 s in `_fnx.adjacency_arrays`.
- After profile: `profile_to_scipy_weighted_float_after.txt`; five calls spend 0.119 s in `_fnx.adjacency_default_order_arrays`.

One lever:
- Added `_fnx.adjacency_default_order_arrays` for exact `Graph`, default nodelist, dtype-pinned weighted CSR export.
- The helper walks cached neighbor-index slices and synced Rust edge attrs, avoiding Python nodelist canonicalization and per-edge string-to-index lookup.
- Explicit nodelists, DiGraph, MultiGraph, non-CSR, non-string weights, and fallback routes continue through the previous helper or Python path.

Behavior isomorphism:
- Node ordering is unchanged: the optimized route is gated to `nodelist is None`, so rows/cols use graph insertion order, identical to `list(G)`.
- Neighbor/tie ordering is CSR-observable equivalent: the new helper emits by row adjacency insertion order and returns CSR only; CSR canonicalization preserves the same matrix payload.
- Self-loop behavior is unchanged: cached neighbor index slices include a self-loop once, matching the previous `ui != vi` duplicate suppression.
- Weight semantics are unchanged: Python-visible edge attrs are synced before the native read, and missing string weights still use default weight `1.0`.
- Floating point bytes are unchanged for the final CSR payload; the same `f64` values feed SciPy COO/CSR construction with `dtype=float`.
- RNG is not used by the optimized export path; the benchmark graph construction seed is unchanged.

Golden output:
- Baseline fnx digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`.
- After fnx digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`.
- NetworkX digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`.

Benchmarks:
- Full sparse sweep fnx mean: 0.03611773560114671 s -> 0.030136086599668488 s.
- Full sparse sweep fnx median: 0.036253477999707684 s -> 0.028870590002043173 s.
- Full sparse sweep fnx-vs-NetworkX ratio: 1.3322909088406472 -> 0.9582594987957694.
- Disabled-lever sampled fnx mean: 0.04560958200090681 s -> 0.04024373924767133 s.
- Disabled-lever sampled fnx median: 0.037449499002832454 s -> 0.033399825493688695 s.
- Hyperfine process mean: 0.7722733718885715 s -> 0.7451440798885715 s.
- Hyperfine process median: 0.77210965346 s -> 0.7320565604600001 s.

Score:
- Impact 2 x Confidence 4 / Effort 2 = 4.0.
- Verdict: keep.
