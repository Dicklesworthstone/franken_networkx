# br-r37-c1-e92fj pass 9: Louvain randbelow bit-count keep

## Candidate

Change exactly one native Louvain shuffle primitive:

```rust
let bit_count = usize::BITS - upper_bound.leading_zeros();
```

The previous code used `(upper_bound - 1).leading_zeros()`, which implements
`(n - 1).bit_length()`. CPython `Random._randbelow(n)`, used by
`seed.shuffle(rand_nodes)` in NetworkX Louvain, uses `n.bit_length()`.

Unchanged:

- MT19937 seed state model.
- Fisher-Yates loop structure.
- Node order before shuffle.
- Gain formula and gain epsilon.
- Neighbor/community iteration.
- Floating-point arithmetic.
- Coarsening.
- Public Python routing.

## Baseline

- Golden: `louvain_pass9_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=11/18`
- Golden SHA: `3815ffb63e89fa3ec4e9995545908b9c5959dc2f33aa16f1530b7c04194a1169`
- Normalized full output SHA without path/timing: `914bd50503ed9eddbaefae14d2223e33ff94ee522aa6c112b30818e825c97fef`
- Public/NX-only normalized SHA: `086564b2d8adc5792944bb99ed4ea5d666be97849e7bd93c6b1a2457868929b8`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26196326704s`, stddev `0.01703057121s`

## Candidate Result

- Golden: `louvain_pass9_after_randbelow_bitcount_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `8bd7078aa871c53273fba99505841efc7b64daec76835c339e31e9d3358f0fc8`
- Normalized full output SHA without path/timing: `3484bd2ef71a9bb9af82965fc638b2f168bb52786358b9059eee16c8e8949a68`
- Public/NX-only normalized SHA: `086564b2d8adc5792944bb99ed4ea5d666be97849e7bd93c6b1a2457868929b8`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26837079428s`, stddev `0.01590329758s`

Remaining raw failures:

```text
ws_150 seed=0
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed on `vmi1227854`.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed on `vmi1153651`, 6 tests.
- Candidate `maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed on `hz1`.
- `sha256sum -c louvain_pass9_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass9_after_randbelow_bitcount_golden.sha256`: passed.
- `cargo fmt -p fnx-algorithms --check`: still fails on pre-existing unrelated formatting drift outside Louvain; no unrelated formatting was normalized in this commit.

## Verdict

Kept as a parity-unlock lever.

This does not enable the public route yet and does not claim a focused raw speed
win: the raw `ws_300 seed=7` timing shifted from `0.26196326704s` to
`0.26837079428s`, inside the same noisy band but directionally slower. The
impact is semantic: raw corpus failures drop from `11/18` to `4/18`, and public
NetworkX-observable output is unchanged.

Score: Impact `4` x Confidence `4` / Effort `1` = `16.0`.

Next target: the remaining failures all sit in Watts-Strogatz cases. Compare the
remaining raw partitions against NetworkX at the shuffle sequence and first
level move trace; the next likely primitive is exact CPython seed-state
initialization or level-to-level RNG consumption, not another neighbor-order
microlever.
