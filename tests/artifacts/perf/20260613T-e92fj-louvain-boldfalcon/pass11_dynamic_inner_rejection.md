# br-r37-c1-e92fj pass 11: dynamic inner partition rejected

## Candidate

Preserve mutable first-level Louvain community membership during `_one_level`:

- Initialize `inner_partition` as singleton communities.
- On a move, remove the node from its old community vector and append it to the target community vector.
- Return filtered surviving communities from that live structure instead of reconstructing them from `node_to_community` in node-index order.

Unchanged:

- Pass 9 `randbelow(n)` behavior.
- RNG seed state.
- Node shuffle.
- Neighbor/community gain scan.
- Gain formula and epsilon.
- Floating-point arithmetic.
- Coarsening edge aggregation.
- Public Python routing.

## Baseline

- Golden: `louvain_pass11_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `df2b1827091c190ba612c5dfc8ba890132ecd350fe4583b05c60321b2de346dc`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.27749765444s`, stddev `0.01642818399s`

## Candidate Result

- Golden: `louvain_pass11_after_dynamic_inner_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `d32c8c925bc23ca275f25865de893ce76ec39a22c82065821e0c9301df24b2fd`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26270542360s`, stddev `0.01575957386s`

Restored state:

- Golden: `louvain_pass11_restored_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `c14c5e5860c4b0011e47c757f1628c041077c56f148050824157e0e4566cd7ef`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed on `vmi1227854`.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed on `vmi1264463`, 6 tests.
- Candidate `maturin develop --release --features pyo3/abi3-py310`: passed.
- Restored `maturin develop --release --features pyo3/abi3-py310`: passed.
- `sha256sum -c louvain_pass11_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass11_after_dynamic_inner_golden.sha256`: passed.
- `sha256sum -c louvain_pass11_restored_golden.sha256`: passed.

## Verdict

Rejected and reverted.

The candidate changed no normalized raw/public outputs and kept raw failures at
`4/18`. The focused timing row improved in this run, but the delta is inside
the noisy band and does not clear the semantic gate. Score is below the keep
threshold.

Next target: compare a first-level NetworkX move trace against the raw Rust
move sequence for `ws_150 seed=0` or `ws_300 seed=7`. The remaining residual is
not explained by survivor community reconstruction order.
