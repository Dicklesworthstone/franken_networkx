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


