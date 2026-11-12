# br-r37-c1-e92fj pass 8: explicit Louvain neighbor rows rejected

## Candidate

Change only the native Louvain one-level neighbor substrate:

- Add explicit `LouvainLevelGraph::neighbors` rows for the initial graph using `Graph::neighbors_indices`.
- Accumulate `weights_to_community` in first-seen row order instead of sorted `BTreeMap` key order.
- Leave RNG, gain threshold, floating-point math, coarsening edge order, output-order conversion, and public Python routing unchanged.

Hypothesis: NetworkX `_one_level` builds `nbrs` from `G[u].items()`, so raw Rust needed a true per-node adjacency row instead of rows reconstructed from global deduped edge order.

## Baseline

- Golden: `louvain_pass8_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=11/18`
- Golden SHA: `c26859be1ecca0bd24dd67e9fae585fbdae2a4dc7f0c9c007b028a218eafd40b`
- Normalized output SHA without path/timing: `914bd50503ed9eddbaefae14d2223e33ff94ee522aa6c112b30818e825c97fef`
- Public-only normalized SHA: `065a448a68c3dfb8c7c03bb4fe418c487c3017e30da8d0ca340da231e5182109`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26044795548s`, stddev `0.00723202288s`

## Candidate Result

- Golden: `louvain_pass8_after_neighbor_rows_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=11/18`
- Golden SHA: `e9b99d8c38b7ecac1adbad9f8789cd9a6020bd20320f7bee77952aab557e3cae`
- Normalized output SHA without path/timing: `e75d390ef6f295daf120b5d75389eb6376154d3441d3780ea09a9269d8cf41c6`
- Public-only normalized SHA: `065a448a68c3dfb8c7c03bb4fe418c487c3017e30da8d0ca340da231e5182109`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.28029127876s`, stddev `0.01607252858s`

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed, 6 tests.
- Candidate `maturin develop --release --features pyo3/abi3-py310`: passed.
- Restored `maturin develop --release --features pyo3/abi3-py310`: passed.
- Restored golden: `public_failures=0/18`, `raw_failures=11/18`.
- Restored normalized output SHA without path/timing: `914bd50503ed9eddbaefae14d2223e33ff94ee522aa6c112b30818e825c97fef`.

## Verdict

Rejected and reverted.

This lever preserved public behavior but changed the raw internal partition artifact without reducing raw failures, and it regressed the focused raw benchmark from `0.26044795548s` to `0.28029127876s`. Score is below the keep threshold.

Next target: the remaining membership failures are not explained by initial neighbor-row order. Attack exact NetworkX partition mutation and set-materialization semantics next, especially how moved nodes are removed/inserted in mutable `set` communities and how that interacts with subsequent coarsened graph node order.
