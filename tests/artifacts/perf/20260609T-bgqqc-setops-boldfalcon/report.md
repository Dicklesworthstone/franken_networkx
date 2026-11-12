# br-r37-c1-bgqqc - simple Graph set-op construction tax

## Lever

Materialize the simple-Graph filtered edge lists in `difference` and
`symmetric_difference` before calling `R.add_edges_from`. This lets the existing
native list/tuple `Graph.add_edges_from` batch path build the fresh no-data
result, instead of feeding a generator through the Python wrapper edge by edge.

Score: `8.0` (`Impact 3 * Confidence 4 / Effort 1.5`).

## Baseline

- Proof SHA: `c4cac7cb9cc05c026e70661289ec7e51b248224c3f8667237a905a33a81f443a`
- Direct `symmetric_difference(Graph, n=1600)` median: `0.0121248215s`
- Direct `difference(Graph, n=1600)` median: `0.0070020480s`
- Hyperfine FNX symmetric-difference loop mean: `0.8695377437s`
- Hyperfine NetworkX symmetric-difference loop mean: `0.6834271493s`

Profile signal: baseline cProfile put `0.348s / 0.724s` under
`add_edges_from` during the looped simple-Graph symmetric-difference workload.

## Final

- Proof SHA: `c4cac7cb9cc05c026e70661289ec7e51b248224c3f8667237a905a33a81f443a`
- Direct `symmetric_difference(Graph, n=1600)` median: `0.0083221395s`
- Direct `difference(Graph, n=1600)` median: `0.0052328630s`
- Hyperfine FNX symmetric-difference loop mean: `0.7183813385s`
- Hyperfine NetworkX symmetric-difference loop mean: `0.6127607402s`

Delta:

- Direct symmetric difference: `1.46x` faster by median.
- Direct difference: `1.34x` faster by median.
- Hyperfine symmetric-difference loop: `1.21x` faster by mean.

## Isomorphism

- Ordering preserved: yes. `difference` still emits G-only edges in `G.edges()`
  order; `symmetric_difference` still emits G-only then H-only edges.
- Tie-breaking unchanged: yes. Node-set checks, graph type checks, and set
  membership semantics are unchanged.
- Floating-point: N/A.
- RNG: N/A.
- Golden outputs: `sha256sum -c proof_files.sha256` passed; baseline and final
  proof payloads have the same embedded result SHA.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py .../harness_setops.py`
- `pytest tests/python/test_setops_order_parity.py ... -q`: `90 passed`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed locally through rch fallback
- `cargo fmt -p fnx-python --check`: blocked by pre-existing Rust formatting drift in `crates/fnx-python/src/{algorithms.rs,digraph.rs,lib.rs,readwrite.rs}`
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by pre-existing `fnx-generators` unused `must_use` warnings
