# br-r37-c1-04z53.79 random_powerlaw_tree_sequence incremental validity

## Target

- Profile-backed follow-up after `br-r37-c1-04z53.78`.
- Case: `random_powerlaw_tree(n=300, gamma=3, seed=5, tries=1000)`.
- Baseline residual: FNX median 0.001093761995s vs NX median 0.000669077010s, 1.634733x slower.
- Baseline profile: `random_powerlaw_tree_sequence` calls `is_valid_tree_degree_sequence` 33 times, `all` 34 times, and scans 9933 generator items.

## One Lever

Maintain `degree_sum` and `nonpositive_degrees` incrementally across the same swap loop instead of rescanning `zseq` on every validity check.

## Isomorphism Proof

- RNG order: unchanged. The initial `n` `paretovariate` calls, the `tries` swap `paretovariate` calls, and the per-failed-check `rng.randint(0, n - 1)` calls occur at the same program points as before.
- Swap order: unchanged. `swap.pop()` is still executed once after each failed validity check, so replacement values are consumed from the same end of the same list.
- Sequence validity semantics: unchanged. For `len(zseq) == 1`, validity is still `zseq[0] == 0`. For longer sequences, validity remains "all degrees >= 1 and sum == 2 * (len - 1)"; the candidate maintains those two predicates incrementally.
- Node and edge order: unchanged. `degree_sequence_tree` receives the same `zseq` and still emits the same backbone and leaf-edge order.
- Tie-breaking: unchanged. No sorting, dict/set iteration, heap order, or comparator was added.
- Floating point: unchanged after the existing `round(paretovariate(...))` calls. The edit only updates integer counters derived from the rounded/clamped sequence.
- Error behavior: unchanged for nonpositive integer `n`, `tries == 0`, and exhausted attempts; the loop count and raise site are unchanged.

## Golden Output

- Baseline FNX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Baseline NX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Candidate FNX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Candidate NX SHA256: `9acb9600008103deee5400c8f4c3b8354aedf03072c9a4c936cdbaa024d92aec`
- Golden artifact SHA256: `9467bfdb009f38e628da087d329e36c1429b2019a5b1664c26a303ca7514b51d` for both baseline and candidate golden JSON.

## Benchmark

Command family: `rch exec -- python3 random_powerlaw_tree_harness.py ...` through the baseline/candidate bundles in this directory.

| Impl | Median seconds |
| --- | ---: |
| Baseline FNX | 0.001093761995 |
| Candidate FNX | 0.000921746003 |
| Baseline NX | 0.000669077010 |
| Candidate NX | 0.000621056010 |

- Same-case FNX speedup: 1.186620x.
- Baseline FNX/NX: 1.634733x slower.
- Candidate FNX/NX: 1.484159x slower.

## Profile Delta

- Function calls: 18786 -> 9025.
- `is_valid_tree_degree_sequence`: 33 calls -> 0 calls.
- `all`: 34 calls -> gone from the top profile.
- Full-sequence validity generator iterations: 9933 -> 0.

## Score

- Impact: 1.186620x.
- Confidence: 4.0, because golden SHA, RNG-order proof, and profile mechanism match.
- Effort: 1.0.
- Score: 4.746, keep.

## Verification

- `python3 -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260613T-rpt-sequence-validity-boldfalcon/random_powerlaw_tree_harness.py`: passed.
- Focused pytest through `rch exec -- python3 -m pytest ...`: passed, `5 passed in 1.15s`.
- Direct edge-case parity probe: `n=1, tries=20`, `n=5, tries=0`, and `n=8, tries=200` matched NetworkX success/error behavior and sequence output.
- `rch exec -- cargo check -p fnx-python --lib`: passed on `vmi1152480`; only pre-existing `fnx-generators` `unused_must_use` warnings were emitted.
- `rch exec -- cargo fmt -p fnx-python --check`: failed on pre-existing Rust formatting drift in `crates/fnx-python/src/algorithms.rs`, `digraph.rs`, `lib.rs`, and `readwrite.rs`. No Rust files were edited for this bead.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: failed on pre-existing `fnx-generators` `unused_must_use` errors at `crates/fnx-generators/src/lib.rs:538`, `621`, `666`, `6218`, and `6758`. No Rust files were edited for this bead.
- `timeout 90s ubs python/franken_networkx/__init__.py .skill-loop-progress.md tests/artifacts/perf/20260613T-rpt-sequence-validity-boldfalcon/random_powerlaw_tree_harness.py tests/artifacts/perf/20260613T-rpt-sequence-validity-boldfalcon/proof.md`: timed out during Python scan and produced no finding before timeout.

## Alien-Graveyard Mapping

The primitive is incremental certificate maintenance: replace repeated whole-structure validity scans with maintained sufficient statistics while preserving the original stochastic process and output ordering.
