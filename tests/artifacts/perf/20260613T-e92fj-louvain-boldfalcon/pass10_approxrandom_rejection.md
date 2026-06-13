# br-r37-c1-e92fj pass 10: ApproxRandom Louvain RNG state rejected

## Candidate

Switch the native Louvain seeded RNG state from the local `MT19937` seeding
helper to the existing `ApproxRandom` CPython-compatible seed/getrandbits path.

Unchanged:

- Pass 9 `randbelow(n)` bit-count behavior.
- Fisher-Yates shuffle loop.
- Node order before shuffle.
- Gain formula and gain epsilon.
- Neighbor/community iteration.
- Floating-point arithmetic.
- Coarsening.
- Public Python routing.

## Baseline

- Golden: `louvain_pass10_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `9b5b3aa4bba63f409fc30c0035fe101fc1be3565b83ed6e3aa75f0abd4198a6d`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.25575119756s`, stddev `0.01308004394s`

## Candidate Result

- Golden: `louvain_pass10_after_approxrandom_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `d1b274180afaf8acb0ca93411102afae4068e75b2f58ab112c664378503a33ec`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.25769212652s`, stddev `0.00863988653s`

Restored state:

- Golden: `louvain_pass10_restored_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `fecf122846dc1438d6a15c43df7929a2afe0de95bbcbe8efa6ad91a3bd173089`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed on `hz1`.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed on `vmi1156319`, 6 tests.
- Candidate `maturin develop --release --features pyo3/abi3-py310`: passed.
- Restored `maturin develop --release --features pyo3/abi3-py310`: passed.
- `sha256sum -c louvain_pass10_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass10_after_approxrandom_golden.sha256`: passed.
- `sha256sum -c louvain_pass10_restored_golden.sha256`: passed.

## Verdict

Rejected and reverted.

The candidate changed no normalized raw/public outputs, kept raw failures at
`4/18`, and shifted focused timing from `0.25575119756s` to `0.25769212652s`.
Score is below the keep threshold.

Next target: instrument or derive a first-level move trace for the four
Watts-Strogatz residuals. The remaining gap is no longer explained by
randbelow bit count or seed-state replacement.
