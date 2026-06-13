# br-r37-c1-wxy3x pass 4: survivor-orientation rejection

Date: 2026-06-13
Worktree: `/data/projects/.scratch/franken_networkx-wxy3x-cnm-boldfalcon-20260613T0015`

## Candidate

Test the narrow hypothesis that Rust's raw CNM kernel diverges from NetworkX
because it normalizes heap pairs and merges the higher community id into the
lower id, while NetworkX pops `(u, v)` from `MappedQueue` and merges `u` into
`v`.

The attempted lever kept the existing heap comparator but made the popped
`cj` community survive.

## Decision

Rejected. The attempted lever produced the same golden hash and the same single
remaining raw mismatch.

```text
before: 7d65bb29fc6d55116fd55f97b39292b1d7c5b8d1993326b22d1986d8fa1a2f19
after:  7d65bb29fc6d55116fd55f97b39292b1d7c5b8d1993326b22d1986d8fa1a2f19
```

`sha256sum -c candidate_golden_pass4.sha256` passes.

Remaining failure:

- `watts_strogatz_300`: NetworkX returns 5 communities; raw Rust returns 6.

The Rust hunk was manually reverted. No production code is changed by this
pass.

## Verification

- Attempted lever rebuilt with `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
- Rebuilt canonical venv again after reverting the Rust hunk.
- Focused community pytest passed: `3 passed`.
- `rch exec -- cargo check -p fnx-algorithms --all-targets` passed.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings` passed on a pinned worker after one worker lacked `cargo-clippy`.

## Next Target

The remaining gap is not explained by simple survivor-id orientation. Next pass
should compare NetworkX's exact `MappedQueue` row-max update behavior and public
max-Q level-selection semantics against the current Rust heap/global-delta loop.
