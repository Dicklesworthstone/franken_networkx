# br-r37-c1-04z53.9137: MultiGraph compact pair counter

## Target

`multigraph_attr` construction remained slower than NetworkX after the view
and sparse-mirror rejects. Fresh local baseline:

- Survey ratio: `1.2435128062343532`.
- FNX median: `0.018995872989762574s`; NetworkX median:
  `0.015275976969860494s`.
- Focused profile total: `10.025s` over 160 construction/digest loops.
- `_try_add_attr_edges_from_batch`: `2.843s`.
- Golden digest:
  `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.

## Change

The fresh exact-int attributed MultiGraph batch now counts canonical pair keys
with an encoded `u64` ordered-index key instead of `HashMap<(usize, usize),
usize>`. The existing string-lex endpoint ordering is still computed before
encoding, so NetworkX-observable undirected key allocation is unchanged.

## Result

Kept as a small profile-backed construction win.

- Focused profile total: `10.025s -> 9.342s`.
- `_multigraph_attr`: `3.435s -> 3.221s`.
- `_multi_add_edges_from`: `2.942s -> 2.766s`.
- `_try_add_attr_edges_from_batch`: `2.843s -> 2.679s`.
- Survey FNX median: `0.018995872989762574s -> 0.0186067660106346s`.
- Survey ratio: `1.2435128062343532 -> 1.227111382995698`.
- Hyperfine FNX mean was neutral within noise:
  `2.77998234188s -> 2.78067777992s`.
- Hyperfine FNX median was neutral within noise:
  `2.79160554688s -> 2.8008283139200003s`.

Score: `2.4` (`Impact 1.6 x Confidence 1.5 / Effort 1.0`). The keep is based
on same-run focused profile and survey movement, with hyperfine treated as
neutral rather than confirmatory.

## Behavior Proof

- `multigraph_attr` digest parity stayed true.
- Golden digest stayed unchanged:
  `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`.
- Preserves node order, edge order, string-lex undirected pair canonicalization,
  duplicate auto-key sequencing, copied source dictionaries, bool/int fallback,
  and live edge attribute dictionary behavior.
- This path has no floating-point or RNG ordering beyond the preserved attribute
  values and weighted-degree parity already covered by focused tests.

## Validation

- `cargo fmt --check`
- `cargo check -p fnx-python --all-targets`
- `maturin develop --release --features pyo3/abi3-py310`
- `pytest tests/python/test_add_edges_attr_batch_parity.py::test_multigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies -q`
- `pytest tests/python/test_add_edges_attr_batch_parity.py -q`
- `cargo clippy -p fnx-python --all-targets -- -D warnings`
