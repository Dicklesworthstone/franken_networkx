# DiGraph Attributed Construction Lazy Node Attr Mirrors

Bead: `br-r37-c1-04z53.82`

## Target

Fresh construction survey showed `DiGraph.add_edges_from` with attributed
3-tuples as the largest current construction residual:

- Fixture: 2000 nodes, 8000 seeded random directed edge tuples, each with
  `{"weight": 1.0}`.
- Baseline FNX direct median: `0.027365671994630247s`.
- Baseline NetworkX direct median: `0.009304969978984445s`.
- Baseline ratio: FNX was `2.9409737007681316x` slower than NetworkX.
- Baseline cProfile: `_try_add_edges_from_batch` consumed `2.415s` over 100
  constructions.

## One Lever

`PyDiGraph::add_attr_edge_batch` no longer creates an empty Python
`node_py_attrs` dict for each node discovered only through an attributed edge
batch. DiGraph node views already materialize the canonical empty dict lazily
on first `G.nodes[n]` or `G.nodes(data=True)` access, matching the existing
PyGraph batch behavior.

No ordering, tie-break, floating-point, or RNG logic changed. Runtime code does
not consume randomness; the harness fixture uses deterministic `random.Random(2)`.

## Results

- Candidate FNX direct median: `0.01953944901470095s`.
- Direct median speedup: `1.4005344763837027x`.
- Direct mean speedup: `1.4263408393126877x`.
- Candidate FNX direct ratio vs NetworkX control: `2.099893826506843x` slower.
- Hyperfine FNX mean: `1.18314456352s -> 0.8794858966800001s`.
- Hyperfine FNX mean speedup: `1.3452683755206205x`.
- Hyperfine FNX median speedup: `1.3043170913419566x`.
- Candidate hyperfine ratio vs NetworkX control: FNX remained
  `1.3159217247310624x` slower.
- Candidate cProfile: `_try_add_edges_from_batch` consumed `1.602s` over 100
  constructions.
- Native batch profile speedup: `1.5074906367041198x`.

## Isomorphism And Golden Proof

- Ordered node/edge(data=True) construction digest:
  `e603205862fdf5e9ed648d992331f9f236208d0d0bb5743ab01a1103a678c144`.
- Node-attribute lazy-materialization semantic digest:
  `334a1d40c776f5539620631bb1564c19a8cb7f5b5187bc120784808a2a264bd3`.
- Both digests match NetworkX exactly in candidate artifacts.
- The semantic proof covers `copy()` before node attr touch,
  `G.nodes[n]` writes after edge-created nodes, cached `G.nodes(data=True)`
  reads after attr mutation, and insertion after materialization.

## Validation

- `rch exec -- maturin build --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo check -p fnx-python --lib`: passed.
- `PYTHONPATH=... rch exec -- python -m pytest tests/python/test_mutation_sequence_metamorphic_parity.py tests/python/test_cross_class_ctor_parity.py -q`: 13 passed.
- `git diff --check`: passed.
- `ubs` on changed source/harness/metadata files: passed after the harness
  digest proof comparison switched to `hmac.compare_digest`.
- `cargo fmt --check`: blocked by existing rustfmt drift in unrelated files and
  unrelated regions; no formatter churn applied in this one-lever commit.
- `cargo check` still reports pre-existing unused/dead-code warnings in
  `fnx-generators` and cached iterator helpers outside this lever.

## Score

Impact `1.4005` x Confidence `4` / Effort `2` = `2.80`.

Verdict: keep. The residual remains profile-backed, so the next pass should
attack deeper attributed batch internals rather than wrapper dispatch.
