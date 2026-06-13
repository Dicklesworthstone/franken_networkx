# br-r37-c1-e92fj pass 14: ordered working graph kept

## Candidate

Make the native Louvain working graph preserve NetworkX first-seen order:

- Store per-node Louvain neighbor weights in insertion-order vectors instead of
  `BTreeMap`.
- Build `weights_to_community` in first-seen neighbor-community order.
- Let the current community participate in the same strict-gain scan as every
  other candidate community.
- Accumulate coarsened community-pair edges in first-seen edge order instead of
  sorting by `(left, right, weight)`.

Unchanged:

- MT19937 seed state and `randbelow(n)` bit-count behavior.
- Fisher-Yates node shuffle.
- Louvain modularity gain formula.
- Strict `gain > best_gain` tie behavior.
- Threshold and max-level semantics.
- Python public routing.

## Baseline

- Golden: `louvain_pass13_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=3/18`
- Golden SHA: `006f2fe09e992991eb0944f43be13f2cd5090114efa3a295edc23e10e9ddec11`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26050765550s`, stddev `0.01788831437s`
- Profile: `louvain_pass13_before_profile_raw_ws300.txt`, with `_fnx.louvain_communities`
  dominating the focused raw loop.

Baseline raw failures:

```text
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Candidate Results

- Golden: `louvain_pass13_after_ordered_working_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=0/18`
- Golden SHA: `c88cb4591f1b112073aef8a487547b1e6766f16cbb2a97582851da4286b51406`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.27822776236s`, stddev `0.02022528892s`

The focused raw timing is slower on this microbench, so this is not a direct
raw-speed keep. It is kept as the parity-unlock lever: the native kernel now
matches NetworkX/public output across the fixed Louvain gate and can be routed
through the public API in the next single-lever pass.

## Isomorphism Proof

- Ordering preserved: intentionally changed to NetworkX order. Neighbor
  community weights and coarsened edges now follow first-seen working-graph
  insertion order instead of Rust map sort order.
- Tie-breaking unchanged: the comparison remains strict `gain > best_gain`.
  Including the current community in the same scan matches NetworkX's
  `weights2com` iteration path and does not add a new tie rule.
- Floating-point: formulas are unchanged. Accumulation order now follows the
  NetworkX working graph path; the golden gate verifies the observable result.
- RNG seeds: unchanged MT19937 seed state, randbelow bit-count, and shuffle loop.
- Golden outputs: `sha256sum -c` passed for baseline, rejected candidates, and
  ordered-working candidate artifacts.

## Rejected Probes In This Pass

- `after_current_gain`: worsened raw failures from `3/18` to `4/18`.
- `after_current_loop`: kept raw failures at `3/18` but changed which seed
  failed, fixing `ws_300 seed=1` while reintroducing `ws_150 seed=0`.

Those probes showed current-community participation alone was insufficient; the
full first-seen working-graph order was the behavior-changing primitive.

## Validation

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed
  with pass-specific `CARGO_TARGET_DIR`.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed, 6 tests.
- `rch exec -- cargo check -p fnx-algorithms --lib`: passed.
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed.
- `git diff --check`: passed.
- `sha256sum -c louvain_pass13_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_current_gain_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_current_loop_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_ordered_working_golden.sha256`: passed.
- `ubs crates/fnx-algorithms/src/lib.rs`: exited nonzero on broad pre-existing
  findings in the same large file; its internal fmt, clippy, check, and test
  build subchecks were clean.

## Score

Impact `5` x Confidence `5` / Effort `3` = `8.33`.

The impact is the removal of the final raw Louvain parity blocker
(`3/18 -> 0/18`), which unlocks the next public native-route speed lever.

## Next Target

Route the public simple-graph `fnx.community.louvain_communities` path to the
now-exact native kernel behind the existing guard surface, then re-baseline and
verify the public benchmark delta.
