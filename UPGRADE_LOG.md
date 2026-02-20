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
