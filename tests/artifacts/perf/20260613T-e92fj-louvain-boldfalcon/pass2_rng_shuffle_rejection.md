# Pass 2 - Louvain CPython RNG/shuffle semantic lever

Bead: `br-r37-c1-e92fj`

Mission: test exactly one raw Rust Louvain semantic lever: replace the
Louvain-only `louvain_seed_rng` / `louvain_randbelow` / `louvain_shuffle`
MT19937 helper with the existing CPython-compatible `ApproxRandom::randbelow`
shuffle semantics from `crates/fnx-algorithms/src/lib.rs`.

## Candidate

- Changed `louvain_seed_rng` to return `Option<ApproxRandom>`.
- Changed `louvain_shuffle` to call `rng.randbelow(index + 1)`.
- Changed `louvain_one_level` to accept `Option<&mut ApproxRandom>`.
- Did not change coarsening, modularity math, output ordering, Python wrapper
  routing, or tests.

## Result

Rejected. The candidate did not improve raw parity, so the Rust hunk was
reverted and only this evidence was kept.

| Artifact | SHA-256 | Public failures | Raw failures |
| --- | --- | ---: | ---: |
| `louvain_pass1_golden.json` | `93a1ee03fa7c1ed7c9c258ab98a96fa77b7f0a61c17ba364383e30331054b027` | 0/18 | 15/18 |
| `louvain_pass2_before_golden.json` | `7037dc87c935c0ec31b194864c64301491b0528a4eb6131fa5168af717eaf118` | 0/18 | 15/18 |
| `louvain_pass2_after_golden.json` | `d0732621456175d1b9182528840407e9eedcf05a57edf6135cfd567385bb2def` | 0/18 | 15/18 |

## Commands

```bash
python3 tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1_harness.py golden \
  --output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass2_before_golden.json \
  --sha-output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass2_before_golden.sha256

CARGO_TARGET_DIR=/tmp/fnx_louvain_pass2_target \
  rch exec -- maturin build --release --features pyo3/abi3-py310 \
  -o /tmp/fnx_louvain_pass2_wheels_clean

PYTHONPATH=/tmp/fnx_louvain_pass2_pkg_clean_20260613T0311_4153242 \
  python3 tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1_harness.py golden \
  --output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass2_after_golden.json \
  --sha-output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass2_after_golden.sha256

(cd tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon && \
  sha256sum -c louvain_pass1_golden.sha256 && \
  sha256sum -c louvain_pass2_before_golden.sha256 && \
  sha256sum -c louvain_pass2_after_golden.sha256)

RCH_REQUIRE_REMOTE=1 rch exec -- cargo check -p fnx-algorithms --lib
RCH_REQUIRE_REMOTE=1 rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings
```

Validation results:

- `louvain_pass1_golden.json: OK`
- `louvain_pass2_before_golden.json: OK`
- `louvain_pass2_after_golden.json: OK`
- Remote `cargo check -p fnx-algorithms --lib`: passed on `vmi1149989`.
- Remote `cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed on
  `vmi1149989`.

## Isomorphism

- Ordering preserved: candidate kept the existing Fisher-Yates loop and node
  order input.
- Tie-breaking unchanged: candidate only changed RNG draws feeding the same
  shuffle; all gain comparisons and `BTreeMap` iteration remained unchanged.
- Floating-point: unchanged.
- RNG seeds: candidate used the existing CPython-compatible `ApproxRandom`
  seed/randbelow path, but this did not reduce corpus failures.
- Golden outputs: all recorded SHA checks pass.
