# br-r37-c1-tp7j4 caveman native constructor

## Lever

Route exact non-negative Python `int` calls to `caveman_graph(l, k)` through a
native `caveman_graph_native` constructor. The wrapper still owns NetworkX's
negative and odd argument behavior; only the profiled `caveman_graph(50, 50)`
shape bypasses Python edge tuple generation and generic `add_edges_from`
decoding.

## Proof

- Golden proof SHA before: `65d461c7fec7771d218887b44ea05add6e8c8cea8ff315e4d560851c39f1b718`
- Golden proof SHA after:  `65d461c7fec7771d218887b44ea05add6e8c8cea8ff315e4d560851c39f1b718`
- Caveman graph digest before/after/NX: `ffb042f383bd2fdc22ecf321f9d0cb1209c0efa7a372b514ebfe2172300e00fe`
- Ordering/tie-breaking/RNG: deterministic structural generator; proof covers
  node order, adjacency row order, and edge order across the generator sweep.

## Benchmark

`rch exec -- hyperfine`, release editable builds, loop50:

- Before FNX: `2.53194224278 s +/- 0.09995937872`
- After FNX: `1.11729818868 s +/- 0.08546950895`
- FNX self-speedup: `2.27x`
- Before NetworkX comparator: `2.25856377958 s +/- 0.05337710191`
- After NetworkX comparator: `2.26758244208 s +/- 0.10138800180`
- Position moved from `1.12x slower than nx` to `2.03x faster than nx`.

Direct harness medians:

- Before FNX: `55.289885 ms`
- After FNX: `14.317465 ms`
- Before NetworkX: `31.939948 ms`
- After NetworkX: `28.464596 ms`
- Direct FNX self-speedup: `3.86x`

## Profile

Before: 612,586 calls / 0.585s for 5 builds; `add_edges_from` and tuple
generation dominated (`_try_add_edges_from_batch` alone 0.316s).

After: 81 calls / 0.141s for 10 builds; time is concentrated in
`franken_networkx._fnx.caveman_graph_native`.

## Validation

- `cargo check -p fnx-python --all-targets`: pass; pre-existing warnings in
  `fnx-generators` and `fnx-algorithms`.
- `cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings`: blocked
  by pre-existing `collapsible_if` lints in unrelated files.
- `cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings -A clippy::collapsible_if`: pass.
- `cargo fmt -p fnx-python --check`: blocked by pre-existing formatting drift
  in unrelated files; no formatter diff for touched files.
- Targeted pytest: `15 passed`.
- UBS on touched files: Rust scan finished; Python scan on the 50k-line wrapper
  stayed CPU-bound for more than five minutes and was interrupted.

## Score

Impact `3` x confidence `0.95` / effort `1` = `2.85`, keep.
