# br-r37-c1-f0zo8 Golden And Isomorphism Proof

This file records the behavior preserved by the lazy nested
MultiGraph/MultiDiGraph row-view lever.

## Golden

- Baseline file: `golden_multigraph_nested_atlasview_f0zo8.json`
- Baseline digest:
  `0523652fa10f9dc210f4367d5a582e35313f637b224967739fce853f3f88fb9f`
- After file: `after_golden_f0zo8.jsonl`
- After artifact SHA-256:
  `e2e47e39c2f5b5656a6a6aa171e9666d63cd3f46911cc7318164e15b0516f06f`
- After semantic digest:
  `162feaa5a7906b8f7527a4a51c81c8012ae80e81344cb24906d5b8db1dc6860b`
- Workload: small mixed-key MultiGraph and MultiDiGraph fixtures for semantic
  coverage, separate from the high-degree benchmark workload.

## Coverage

- Neighbor order:
  - MultiGraph FNX: `'alpha'`, `'beta'`, `'gamma'`, `'omega'`, `'delta'`
  - MultiDiGraph FNX: `'alpha'`, `'beta'`, `'gamma'`, `'delta'`
- Edge key order:
  - MultiGraph FNX `hub-alpha`: `2`, `'k0'`, `'late'`
  - MultiDiGraph FNX `hub-alpha`: `2`, `'k0'`, `'late'`
- Live mutation visibility:
  - Mutating `row["alpha"][2]["via_view"]` is visible through a fresh
    `graph["hub"]["alpha"][2]` lookup.
  - Adding a late parallel edge is visible in the retained view.
  - Adding a late neighbor/successor is visible in a fresh row view.
- Copy and dict materialization:
  - `row.copy()` materializes a plain `dict` with inner plain key dicts.
  - `dict(row)` materializes a plain outer `dict` whose values retain the
    current view value shape.
- KeyError parity:
  - Missing node, missing neighbor, and missing edge key all raise `KeyError`
    for FNX and NetworkX.
- Type and repr shape:
  - FNX current public row type is `franken_networkx.AdjacencyView`; inner type
    is `franken_networkx.AtlasView`.
  - NetworkX row type is `networkx.classes.coreviews.AdjacencyView`; inner type
    is `networkx.classes.coreviews.AtlasView`.
  - Reprs are captured in the golden payload.

## Isomorphism Status

- Ordering preserved: `MultiGraph` and `MultiDiGraph` neighbor/successor order
  matches NetworkX in the after golden; edge-key order for parallel edges also
  matches.
- Tie-breaking unchanged: no algorithmic tie-break code touched; view iteration
  follows existing graph storage order.
- Floating-point: N/A for view access.
- RNG seeds: N/A; deterministic fixtures.
- Live mutation visibility preserved: mutating an edge attr dict returned from
  `G[u][v][key]` is visible through a fresh graph lookup; adding/removing edges
  is visible through fresh row views.
- Copy/materialization parity preserved: public row type remains
  `AdjacencyView`, inner type remains `AtlasView`, and `.copy()`/`dict(row)`
  preserve NetworkX-observable shapes.
- KeyError parity preserved: missing node, missing neighbor, and missing edge
  key remain `KeyError` with the original public key object.
- Golden outputs: `sha256sum -c artifact_sha256_f0zo8.txt` validates the after
  golden, benchmark, profile, and validation artifacts listed in the ledger.

## Changed Surfaces

- `crates/fnx-python/src/lib.rs`
- `crates/fnx-python/src/digraph.rs`
- `python/franken_networkx/__init__.py`

`crates/fnx-python/src/views.rs` was formatted/left behaviorally unchanged by
this lever.

## Validation

- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
  passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets --no-deps -- -D warnings`
  passed.
- `cargo fmt -p fnx-python --check` passed.
- `python3 -m pytest tests/python/test_attribute_access_parity.py -q` passed
  (`143 passed`).
