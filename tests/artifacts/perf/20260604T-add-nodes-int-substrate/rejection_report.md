# add_nodes_int Empty-Range Direct-Map Candidate

Bead: `br-r37-c1-le46a`

## Profile Target

Fresh rch baseline kept `add_nodes_int` profile-backed:

- direct FNX mean `0.08770286199998939s`
- direct NetworkX mean `0.03385548155509039s`
- FNX / NX ratio `2.5905070012747373`
- profile: `0.542s` in native `_fast_add_int_nodes_range_stop` over 9 calls
- hyperfine mean `0.6267187995400001s`

Golden digest matched NetworkX before the edit:
`eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`.

## Candidate Lever

For empty `Graph.add_nodes_from(range(0, stop, 1))`, bypassed per-node
`HashMap::entry` probes in `node_key_map` / `node_py_attrs`, inserted directly,
and bumped `nodes_seq` once by the inserted batch count. Non-empty graphs kept
the existing first-wins path.

## Result

Rejected. The candidate preserved behavior, but did not meet Score >= 2.0:

- direct FNX mean `0.08770286199998939s` -> `0.08252559366519563s` (1.063x)
- hyperfine mean `0.6267187995400001s` -> `0.60963303082s` (1.028x)
- profile native time `0.542s` -> `0.560s` over 9 calls
- golden digest stayed `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

## Isomorphism

- Ordering: unchanged; serialized node order stayed `0..99999`.
- Tie-breaking: unchanged; non-empty and duplicate/equality cases stayed on the
  old first-wins path.
- Floating point: N/A.
- RNG: N/A.
- Golden output: unchanged and equal to NetworkX.

## Verification

- `cargo fmt -p fnx-python --check`: passed for candidate and restored source.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- cargo test -p fnx-python graph_fast_int_range_empty_preserves_node_metadata --features pyo3/abi3-py310 -- --nocapture`: passed for candidate.
- Restored source diff for `crates/fnx-python/src/lib.rs`: empty.
- Restored release extension rebuilt with `rch exec -- maturin develop --release --features pyo3/abi3-py310`.

## Next Primitive

Do not continue entry-probe/counter tweaks on this loop. The profile shows the
remaining structural cost is eager per-node Python metadata allocation. The next
alien primitive is a lazy node-attribute side table with live materialization
guards: keep integer node identity/order in the existing maps, but defer empty
Python attr dict creation until `G.nodes[n]`, `nodes(data=True)`, copy/subgraph,
or attr-sync actually observes/mutates it. Proof obligations are live mutation
persistence, node attr dict identity, order, and NetworkX digest parity.
