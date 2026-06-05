# br-r37-c1-941xy lazy empty metadata

Target: `MultiGraph.add_edge(i, i + 1, key=str(i))`, profile-backed by
`_fast_add_explicit_str_edge` in `br-r37-c1-941xy`.

Lever: keep empty MultiGraph node/edge Python metadata sparse during no-attr
construction; allocate the live `dict` only when a NetworkX-observable mapping
is handed out.

Baseline (`rch exec -- hyperfine`, 10 runs):

- FNX: `733.8 ms +/- 67.2 ms`
- NetworkX: `504.4 ms +/- 24.4 ms`
- Gap: NetworkX `1.45x` faster

After (`rch exec -- hyperfine`, 10 runs):

- FNX: `683.9 ms +/- 33.3 ms`
- NetworkX: `513.4 ms +/- 17.3 ms`
- Gap: NetworkX `1.33x` faster

Profile (`rch exec`, 7 construction samples):

- FNX mean: `0.2862912004 s -> 0.2263517813 s`
- `_fast_add_explicit_str_edge` self: `1.252 s -> 0.960 s` across `350000` calls
- Benchmark digest unchanged: `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`

Correctness proof:

- Script: `parity_proof.py`
- Golden SHA256: `6e2986d966c94f050da591f48357f6d0a22a8bac72a8f00eac811731959e8c73`
- Covers node order, edge/key order, edge data, `get_edge_data`, live edge attr
  dict mutation, live node attr dict mutation, hash-equal key first-wins,
  subgraph/copy preservation, weighted size for missing attrs.
- FP/RNG: no random inputs; only deterministic integer-weight smoke in proof.

Score: `2.4 = Impact 1.0 x Confidence 0.72 / Effort 0.30`.

Gates:

- `rch exec -- cargo check -p fnx-python --all-targets`: pass
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: pass
- `cargo fmt -p fnx-python --check`: pass
- Focused pytest: `489 passed, 414 deselected`
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: pass
  after the separate `views.rs` clippy hygiene fix; the perf commit changes
  only `lib.rs` plus proof artifacts.
