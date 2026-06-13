# br-r37-c1-e92fj pass 12: bounded Louvain gain-floor keep

## Candidate

Apply NetworkX's first-level move acceptance floor after the pass-9 randbelow
fix, while bounding the known floating-point dust cycle:

- Change native Louvain `LOUVAIN_GAIN_EPS` from `1.0e-12` to `0.0`.
- Add a per-level repeated `node_to_community` state guard.

Unchanged:

- MT19937 seed state and pass-9 `randbelow(n)` bit-count behavior.
- Fisher-Yates shuffle loop and node order.
- Neighbor/community iteration order.
- Gain formula and strict `gain > best_gain` comparison.
- Coarsening, output-order conversion, and public Python routing.

## Baseline

- Golden: `louvain_pass12_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=4/18`
- Golden SHA: `f300b3d5373a3057249a9575478665f6031231a2798c455c92360a0f49e9fd9f`
- Stable output SHA: `d65ca6bed66cffd6002a077d419bb49274334a4544f54349b7a2185fdc7234cd`
- Public/NX-only normalized SHA: `649c810bd40743591843af52dde83cb0db44dd204c9046361914c30bc3838a31`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.28377202822s`, stddev `0.02414609785s`

Baseline raw failures:

```text
ws_150 seed=0
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Candidate Result

- Golden: `louvain_pass12_after_bounded_gain_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=3/18`
- Golden SHA: `451132eb174a040350ec3ddf0b97b50c55480175bc18ef9ea1d5e060ac9fb0d4`
- Stable output SHA: `4cf6f7b805d371c2c4a6963dde5a2f3e80f27ea893df9a8b678f848058087010`
- Public/NX-only normalized SHA: `649c810bd40743591843af52dde83cb0db44dd204c9046361914c30bc3838a31`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.31509172202s`, stddev `0.03770782588s`

Remaining raw failures:

```text
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Isomorphism Proof

- Ordering preserved: public/NX-only normalized SHA stayed identical; output-order conversion unchanged.
- Tie-breaking aligned: move scan order and strict `>` comparison unchanged; only the positive-gain floor now matches NetworkX.
- Floating-point: gain formula unchanged; acceptance floor changed to NetworkX's `best_mod = 0`.
- RNG seeds: unchanged MT19937 seed state, shuffle loop, and pass-9 randbelow bit count.
- Golden outputs: `sha256sum -c` passed for before and after artifacts.

## Validation

- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed on `vmi1227854`, 6 tests.
- Candidate `maturin develop --release --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo check -p fnx-algorithms --lib`: passed on `vmi1152480`.
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed on `vmi1152480`.
- `sha256sum -c louvain_pass12_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass12_after_bounded_gain_golden.sha256`: passed.
- `cargo fmt -p fnx-algorithms --check`: still reports pre-existing unrelated formatting drift elsewhere in `crates/fnx-algorithms/src/lib.rs`; this pass did not normalize unrelated formatting.
- `ubs crates/fnx-algorithms/src/lib.rs`: exits nonzero on broad pre-existing findings, including the existing false-positive secret-compare report for `new_group_id != group_of[i]`.

## Verdict

Kept as a parity-unlock lever.

This is not a raw speed win: the focused raw `ws_300 seed=7` timing shifted
from `0.28377202822s` to `0.31509172202s`. The keep reason is semantic: raw
corpus failures drop from `4/18` to `3/18`, public output stays unchanged, and
the previous unbounded zero-gain hang is prevented by the repeated-state guard.

Score: Impact `3` x Confidence `4` / Effort `2` = `6.0`.

Next target: the remaining residual is all `ws_300` first-level behavior. The
next pass should compare first-level move traces around the first divergent
node, especially `sigma_tot` updates and self/current-community handling after
the bounded zero-floor change.
