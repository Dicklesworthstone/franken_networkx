# dfs_edges indexed traversal validation summary

## rch-backed benchmarks

- Baseline direct FNX mean: `0.002140505210554693s`
- After direct FNX mean: `0.0008844071408384479s`
- Baseline hyperfine mean: `0.5674150867333334s`
- After hyperfine mean: `0.49713454514s`
- After confirm hyperfine mean: `0.48957940547999995s`

## Behavior proof

- Golden FNX output SHA unchanged: `4e7e131ed92143a32bf58531ae1877b323e6aafaa8b9137ef190bace6bcacfd5`
- Ordering and tie-breaking preserved by reverse neighbor push and visited-on-pop semantics.
- No floating-point or RNG path changed.

## Code validation

- `cargo fmt --package fnx-algorithms --check`: passed via rch.
- `cargo check -p fnx-algorithms --lib`: passed via rch.
- `cargo test -p fnx-algorithms dfs_edges --lib -- --nocapture`: passed via rch.
- `cargo clippy -p fnx-algorithms --lib --no-deps -- -D warnings`: passed via rch.
- Focused Python traversal parity pytest: 94 passed via rch.
- UBS Rust scan: exit 1 due pre-existing broad findings outside the changed DFS hunk.

Verdict: productive, Score `6.0`, keep and commit.

