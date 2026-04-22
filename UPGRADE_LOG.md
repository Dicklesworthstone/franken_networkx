# Dependency Upgrade Log

**Date:** 2026-02-20  |  **Project:** franken_networkx  |  **Language:** Rust

## Summary
- **Updated:** 8  |  **Already latest:** 3  |  **Failed:** 0

## Toolchain

### Rust nightly
- **Channel:** `nightly` (rolling latest)
- **Current version:** rustc 1.95.0-nightly (7f99507f5 2026-02-19)
- **Status:** Already at latest

## Updated Dependencies

### serde: 1.0.218 -> 1.0.228
- **Scope:** fnx-classes, fnx-dispatch, fnx-convert, fnx-algorithms, fnx-readwrite, fnx-durability, fnx-conformance, fnx-runtime
- **Breaking:** None (patch bump)
- **Tests:** Passed

### serde_json: 1.0.139 -> 1.0.149
- **Scope:** fnx-readwrite, fnx-durability, fnx-conformance, fnx-runtime
- **Breaking:** None (patch bump)
- **Tests:** Passed

### indexmap: 2.7.1 -> 2.13.0
- **Scope:** fnx-classes
- **Breaking:** None (semver-compatible minor bump)
- **Tests:** Passed

### thiserror: 2.0.11 -> 2.0.18
- **Scope:** fnx-durability
- **Breaking:** None (patch bump)
- **Tests:** Passed

### blake3: 1.5.5 -> 1.8.3
- **Scope:** fnx-durability
- **Breaking:** None (semver-compatible minor bump)
- **Tests:** Passed

### tempfile: 3.17.1 -> 3.25.0
- **Scope:** fnx-durability (dev)
- **Breaking:** None (semver-compatible minor bump)
- **Tests:** Passed

### proptest: 1.6.0 -> 1.10.0
- **Scope:** fnx-classes, fnx-convert, fnx-algorithms, fnx-generators, fnx-readwrite, fnx-conformance (dev)
- **Breaking:** None (semver-compatible minor bump)
- **Tests:** Passed

### rand: 0.9.0 -> 0.10.0
- **Scope:** fnx-generators
- **Breaking:** Yes - `rand::Rng` trait renamed to `rand::RngExt`
- **Migration:** Updated `use rand::{Rng, ...}` to `use rand::{RngExt, ...}` in `crates/fnx-generators/src/lib.rs`
- **Tests:** Passed

## Already At Latest

| Crate | Version |
|-------|---------|
| mwmatching | 0.1.1 |
| base64 | 0.22.1 |
| raptorq | 2.0.0 |

## Transitive Updates (via cargo update)

| Crate | From | To |
|-------|------|----|
| anyhow | 1.0.101 | 1.0.102 |
| syn | 2.0.115 | 2.0.117 |
| unicode-ident | 1.0.23 | 1.0.24 |

## Verification

- `cargo check --workspace --all-targets`: Passed
- `cargo clippy --workspace --all-targets -- -D warnings`: Passed
- `cargo fmt --check`: Passed
- `cargo test --workspace`: All tests passed (0 failures)

---

**Date:** 2026-04-21

### asupersync: 0.2.0 -> 0.3.0
- **Scope:** fnx-runtime (optional dep)
- **Breaking:** None
- **Tests:** cargo check passed

---

## Session 2026-04-21 (Clawdstein-libupdater-franken_networkx)

### Scope of this session

Focused bump of `asupersync` to 0.3.1 (fresh on crates.io) followed by a full
library-updater sweep.

### Session Summary

| Metric | Count |
|---|---|
| Considered | 12 |
| Updated | 7 (asupersync, indexmap, proptest, rand, rand_core, blake3, raptorq, tempfile, criterion, + transitive cc) |
| Skipped (already latest) | 9 |
| Deferred (requires attention) | 2 (quick-xml, pyo3 + pyo3-log) |
| Failed (rolled back) | 0 |

### Final commit SHAs (this session)

| Bump | SHA |
|---|---|
| asupersync 0.3.0 -> 0.3.1 | 828b6b3 |
| indexmap 2.13.0 -> 2.14.0 | 60ca816 |
| proptest 1.10.0 -> 1.11.0 | 77d22a4 |
| rand + rand_core 0.10.0 -> 0.10.1 | 0db80a3 |
| blake3/raptorq/tempfile | 18ff286 |
| criterion 0.5 -> 0.8 (+ cc) | d217623 |

### Circuit breakers / budget

No circuit breaker tripped (0 consecutive failures, 0 rollbacks, far under the
25-dep budget). Two major jumps were deliberately deferred on the "requires
attention" track rather than forced through.

### Already At Latest (skipped this session)

| Crate | Pinned at | Notes |
|---|---|---|
| mwmatching | 0.1.1 | at latest |
| mt19937 | 3.3.0 | at latest |
| serde | 1.0.228 | at latest |
| serde_json | 1.0.149 | at latest |
| thiserror | 2.0.18 | at latest |
| base64 | 0.22.1 | at latest |
| hex | 0.4 | semver range covers latest 0.4.3 |
| dhat | 0.3 | semver range covers latest 0.3.3 |
| log | 0.4 | semver range covers latest 0.4.29 |

### Target list

| Crate | From | To | Notes |
|---|---|---|---|
| asupersync | 0.3.0 | 0.3.1 | separate commit (feature-gated) |
| indexmap | 2.13.0 | 2.14.0 | patch/minor |
| proptest | 1.10.0 | 1.11.0 | dev-dep |
| criterion | 0.5 | 0.8.2 | major jump (dev-bench) |
| rand_core | 0.10.0 | 0.10.1 | patch |
| blake3 | 1.8.3 | 1.8.4 | patch |
| raptorq | 2.0.0 | 2.0.1 | patch |
| rand | 0.10.0 | 0.10.1 | patch |
| tempfile | 3.25.0 | 3.27.0 | minor (dev) |
| quick-xml | 0.37.5 | 0.39.2 | minor; known breaking-minor |
| pyo3 | 0.23 | 0.28.3 | major; heavy audit required |
| pyo3-log | 0.12 | 0.13.3 | follows pyo3 major bump |

### Updates

#### asupersync: 0.3.0 -> 0.3.1
- **Scope:** crates/fnx-runtime/Cargo.toml (feature `asupersync-integration`)
- **Breaking:** None (patch); sibling crates franken-kernel/evidence/decision
  also moved 0.3.0 -> 0.3.1 via Cargo.lock.
- **Verification:** `rch exec -- cargo check -p fnx-runtime --features asupersync-integration` green.
- **Commit:** 828b6b3

#### indexmap: 2.13.0 -> 2.14.0
- **Scope:** crates/fnx-classes/Cargo.toml
- **Breaking:** None (minor bump; semver-compatible). Release notes (github.com/indexmap-rs/indexmap) describe new `IndexMap::into_boxed_slice` and misc perf tweaks.
- **Verification:** `rch exec -- cargo check --workspace --all-targets` green; `rch exec -- cargo test -p fnx-classes` green (52 passed).
- **Commit:** 60ca816

#### proptest: 1.10.0 -> 1.11.0
- **Scope:** dev-dependencies of fnx-classes, fnx-convert, fnx-algorithms, fnx-generators, fnx-readwrite, fnx-conformance, fnx-python
- **Breaking:** None (minor bump; semver-compatible).
- **Verification:** `rch exec -- cargo check --workspace --all-targets` green; `rch exec -- cargo test -p fnx-classes -p fnx-algorithms` green.
- **Commit:** 77d22a4

#### rand + rand_core: 0.10.0 -> 0.10.1
- **Scope:** `rand` in fnx-generators, `rand_core` in fnx-algorithms.
- **Breaking:** None (patch bumps).
- **Verification:** `rch exec -- cargo check --workspace --all-targets` green; `rch exec -- cargo test -p fnx-generators -p fnx-algorithms` green (37 passed in fnx-generators suite).
- **Commit:** 0db80a3

#### blake3 1.8.3 -> 1.8.4, raptorq 2.0.0 -> 2.0.1, tempfile 3.25.0 -> 3.27.0
- **Scope:** crates/fnx-durability/Cargo.toml (blake3/raptorq normal deps; tempfile dev-dep).
- **Breaking:** None — all three are patch/minor semver-compatible bumps.
  - `blake3 1.8.4` is a hotfix release. `raptorq 2.0.1` is a patch release in
    the stable 2.0 series. `tempfile 3.27.0` pulls in refreshed `rustix`
    / `linux-raw-sys` transients.
- **Verification:** `rch exec -- cargo check --workspace --all-targets` green; `rch exec -- cargo test -p fnx-durability` green (3 passed).
- **Commit:** 18ff286

#### pyo3 0.23 + pyo3-log 0.12 (DEFERRED - requires attention)

- **Scope:** crates/fnx-python/Cargo.toml — 22,500 lines across 7 `.rs` files
  (`lib.rs`, `algorithms.rs`, `digraph.rs`, `views.rs`, `readwrite.rs`,
  `generators.rs`, `cgse.rs`) all written against the pyo3 0.23 surface.
- **Latest stable:** pyo3 0.28.3, pyo3-log 0.13.3. Five major pyo3 releases
  (0.24 / 0.25 / 0.26 / 0.27 / 0.28) sit between current and target, each
  with its own breaking changes — most notably the hard cutover to the
  `Bound<'py, T>` API, changes to `PyResult` / error conversion, adjustments
  to `#[pymethods]` / `#[pyfunction]` signatures, `intern!`, and the
  freethreaded/no-GIL build path.
- **Risk:** easily touches hundreds of sites across the fnx-python surface —
  well beyond the 20-file refactor circuit-breaker in the library-updater
  skill and the per-dep budget in this session's instructions.
- **Recommendation:** schedule a dedicated "pyo3 upgrade" sprint. Suggested
  path is a staircase: bump to 0.24 first, fix, commit; then 0.25, 0.26,
  0.27, 0.28 — each with `cargo check -p fnx-python` + Python-side smoke
  tests. pyo3-log should track: 0.13 is compatible with pyo3 0.24+.
- **Action:** stayed on pyo3 0.23 / pyo3-log 0.12.

#### quick-xml: 0.37.5 (DEFERRED - requires attention)

- **Scope:** crates/fnx-readwrite/Cargo.toml (GraphML reader/writer).
- **Reason deferred:** quick-xml 0.38 + 0.39 carry several breaking changes that
  together require a correctness-sensitive refactor, not a spec bump:
  - `BytesText::unescape` / `unescape_with` removed; replaced by
    `BytesText::decode` (fnx-readwrite calls `e.unescape()` in 2 places while
    parsing GraphML `<data>` and `<default>` text content).
  - Text events no longer contain escaped payloads — XML entity references are
    now reported as a *separate* new `Event::GeneralRef`. GraphML parsing would
    need to learn to accumulate entity references into the pending text
    buffer; otherwise any `&amp;` / `&lt;` / `&#...;` inside `<data>` is
    silently dropped.
  - `read_text()` returns `BytesText` instead of `Cow<str>`.
  - Several `NsReader` helpers renamed (`.prefixes()`, `.resolve*()`) under a
    `.resolver()` sub-namespace.
  - New `writer::Config` struct replaces individual builder methods.
- **Risk:** silent GraphML round-trip regressions on files containing XML
  entities; correctness-critical for a networkx-compatible reader. No tests in
  fnx-readwrite currently exercise entity-escaped GraphML payload, so a
  naive "replace unescape with decode + ignore GeneralRef" patch would pass
  CI but break real inputs.
- **Recommendation:** schedule a dedicated session to port the GraphML event
  loop to 0.39 (handle `Event::GeneralRef`, add regression tests that embed
  `&amp;`, `&lt;`, and numeric entities in `<data>` payload, then bump).
- **Action:** stayed on 0.37.5.

#### criterion: 0.5 -> 0.8 (fnx-algorithms bench)
- **Scope:** `[dev-dependencies]` of fnx-algorithms (used by the
  `algorithm_benchmarks` bench only; no production code path).
- **Breaking:** None reached us in practice. Between 0.5 and 0.7 criterion
  dropped the `real_blackbox` feature and deprecated `criterion::black_box`
  in favour of `std::hint::black_box`, but `algorithm_benchmarks.rs` does not
  use `black_box` at all. The `Criterion`, `BenchmarkId`, `criterion_group!`,
  and `criterion_main!` surface is unchanged.
- **Transitive side-effect:** the 0.8 jump pulled in a fresh `cc` build-dep
  via `page_size`; the `cc-1.2.56` already in the lock file was incompatible
  with the newer `rustc` (missing `from_rustc_target` / `apple_sdk_name` on
  `TargetInfo`). Ran `cargo update -p cc` to bump cc 1.2.56 -> 1.2.60 and the
  workspace then compiled clean.
- **Verification:** `rch exec -- cargo check --workspace --all-targets` green;
  `rch exec -- cargo test -p fnx-algorithms` green (lib tests + bench harness
  compile).


