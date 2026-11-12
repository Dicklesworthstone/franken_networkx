# br-r37-c1-e92fj pass 13: ordered Louvain working-state keep

## Candidate

Replace sorted/hash aggregation inside native Louvain's working state with
first-seen ordered rows so the Rust kernel preserves NetworkX's mutation and
dict materialization semantics through the whole `_one_level` / coarsen cycle:

- Accumulate level neighbor rows in insertion order instead of sorted `BTreeMap`
  order.
- Accumulate `weights2com` in first-seen neighbor/community order.
- Let the current community participate in the gain scan, matching the
  NetworkX `weights2com.items()` loop.
- Preserve coarsened community-pair edges in first-seen order instead of
  hash-collecting and sorting them.

Unchanged:

- MT19937 seed state and pass-9 `randbelow(n)` bit-count behavior.
- Fisher-Yates node shuffle and node order.
- Gain formula, strict `gain > best_gain` tie behavior, and bounded zero-floor
  repeated-state guard from pass 12.
- Final output conversion and public Python routing.

## Baseline

- Golden: `louvain_pass13_before_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=3/18`
- Golden SHA: `006f2fe09e992991eb0944f43be13f2cd5090114efa3a295edc23e10e9ddec11`
- Stable full-output SHA without timing/path: `43e332216fc56c0fcad69c9c464ba973b0763db47f70ced9a6cfab67517d73ba`
- Public/NX-only normalized SHA: `cf0b092e01b6ca70204ee5fd6d2274cb927809ec60b89cc69b5cf220f4e620fd`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.26050765550s`, stddev `0.01788831437s`

Baseline raw failures:

```text
ws_300 seed=0
ws_300 seed=1
ws_300 seed=7
```

## Candidate Result

- Golden: `louvain_pass13_after_ordered_working_golden.json`
- Raw/public summary: `public_failures=0/18`, `raw_failures=0/18`
- Golden SHA: `c88cb4591f1b112073aef8a487547b1e6766f16cbb2a97582851da4286b51406`
- Stable full-output SHA without timing/path: `014b2826e984cf38965d092f3fe1f3c3ff653c7c649eaa93d3f4c7474d4c4393`
- Public/NX-only normalized SHA: `cf0b092e01b6ca70204ee5fd6d2274cb927809ec60b89cc69b5cf220f4e620fd`
- Hyperfine raw `ws_300 seed=7 loops=20`: mean `0.27822776236s`, stddev `0.02022528892s`

Remaining raw failures:

```text
none
```

## Rejected Subvariants

Two narrower current-community probes were rejected before the ordered-working
primitive was validated:

- `after_current_gain`: public failures stayed `0/18`, raw failures worsened
  `3/18 -> 4/18`, and `ws_150 seed=0` regressed.
- `after_current_loop`: raw failures stayed `3/18`, but the failing set changed,
  fixing `ws_300 seed=1` while reintroducing `ws_150 seed=0`.

Those artifacts are retained in this directory because they show that the keep
requires the ordered working-state primitive, not current-community scanning
alone.

## Isomorphism Proof

- Ordering: public/NX-only normalized SHA stayed identical at
  `cf0b092e01b6ca70204ee5fd6d2274cb927809ec60b89cc69b5cf220f4e620fd`.
- Tie-breaking: strict `gain > best_gain` remains unchanged; the lever changes
  only the order in which NetworkX-equivalent working dictionaries are
  materialized and scanned.
- Floating-point: gain arithmetic and zero-floor acceptance are unchanged from
  pass 12; only accumulation/scan order now follows NetworkX's first-seen
  working-state order.
- RNG: seed state, shuffle loop, and `randbelow(n)` behavior are unchanged.
- Golden outputs: `sha256sum -c` passed for the baseline, rejected subvariant,
  and ordered-working candidate goldens.

## Validation

- `rch exec -- cargo check -p fnx-algorithms --lib`: passed on `vmi1156319`.
- `rch exec -- cargo test -p fnx-algorithms louvain --lib`: passed on
  `vmi1264463`, 6 tests.
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed on
  `vmi1227854`.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `sha256sum -c louvain_pass13_before_golden.sha256`: passed.
- `sha256sum -c louvain_pass13_after_ordered_working_golden.sha256`: passed.
- `cargo fmt -p fnx-algorithms --check`: still fails on unrelated pre-existing
  formatting drift elsewhere in `crates/fnx-algorithms/src/lib.rs`; this pass
  manually applied the only Louvain formatting suggestion.
- `ubs crates/fnx-algorithms/src/lib.rs`: exits nonzero on broad pre-existing
  findings, including the known false-positive secret-compare report for
  `new_group_id != group_of[i]`; UBS's embedded fmt/clippy/build checks were
  clean.

## Verdict

Kept as a parity-unlock primitive.

The focused raw `ws_300 seed=7` timing regressed from `0.26050765550s` to
`0.27822776236s`, so this is not a speed-row keep. The keep reason is semantic
and routing-critical: raw native Louvain now matches NetworkX on the full
18-record fixed-seed corpus, public output remains unchanged, and the raw kernel
can be considered for the next public-route benchmark pass.

Score: Impact `5` x Confidence `4` / Effort `2` = `10.0`.

Next target: reprofile `louvain_communities` with the exact raw kernel now
parity-clean and measure whether the Python public wrapper can safely route to
native for the covered simple-graph cases.
