# Dependency Upgrade Log

**Date:** 2026-09-11  
**Project:** franken_networkx  
**Language:** Rust / Python  
**Manifest:** Cargo.toml, Cargo.lock, pyproject.toml  

---

## Summary

| Metric | Count |
|--------|-------|
| **Total packages locked** | 311 |
| **Updated** | 128 |
| **Skipped / Held** | 2 (`pyo3 0.28.3`, `quick-xml 0.39.4`) |
| **Failed (rolled back)** | 1 (`quick-xml 0.42.0`) |
| **Requires attention** | 1 (`pyo3 0.29` pending `pyo3-log` release) |

---

## Security Advisories Resolved

`cargo update` resolved multiple security and yanked-crate warnings previously flagged by `cargo audit`:
- **`lru`**: 0.18.0 → 0.18.4 (remedies RUSTSEC-2026-0253 panic safety in `LruCache::pop()`)
- **`memmap2`**: 0.9.10 → 0.9.11 (remedies RUSTSEC-2026-0186 unchecked pointer offset)
- **`chacha20`**: updated to 0.10.2 (replaces yanked 0.10.0)
- **`spin`**: updated to 0.10.1 (replaces yanked 0.10.0)

---

## Notable Dependency Updates

- `serde` / `serde_derive`: 1.0.228 → 1.0.229
- `serde_json`: 1.0.150 → 1.0.151
- `thiserror` / `thiserror-impl`: 2.0.18 → 2.0.20
- `blake3`: 1.8.4 → 1.8.7
- `indexmap`: 2.14.0 → 2.14.2
- `rustc-hash`: 2.1.2 → 2.1.3
- `arrayvec`: 0.7.6 → 0.7.8
- `pyo3-log`: 0.13.3 → 0.13.4
- `asupersync`: 0.3.4 → 0.4.11
- `quick-xml`: 0.39.2 → 0.39.4
- `rand`: 0.10.1 → 0.10.2
- `crossbeam-*`: upgraded to latest minor/patch versions
- `futures-*`: upgraded 0.3.32 → 0.3.34
- `regex` / `regex-automata`: upgraded to latest stable
- `zerocopy` / `zerocopy-derive`: 0.8.48 → 0.8.57

---

## Held / Skipped Dependencies

### `quick-xml`: 0.39.4 (available: 0.42.0)
- **Action:** Tested 0.42.0 and rolled back to 0.39.4.
- **Reason:** `quick-xml 0.42.0` introduces a breaking change shifting `attr.key` and `attr.value` from byte slices `&[u8]` to `&str` / `Cow<str>`, causing 41 compilation errors across `fnx-readwrite`. Per `library-updater` rules, large refactors across parsing code require explicit review. Retained on 0.39.4.

### `pyo3`: 0.28.3 (available: 0.29.2)
- **Action:** Held at 0.28.3.
- **Reason:** Upstream `pyo3-log 0.13.4` strictly requires `pyo3 = "0.28"`. Upgrading `pyo3` to 0.29 causes dependency resolution conflict until a compatible `pyo3-log` release is published.

---

## Verification

1. `cargo check --workspace --all-targets` via RCH: **PASSED (107 crates, 0 errors)**
2. `cargo clippy --workspace --all-targets -- -D warnings` via RCH: **PASSED (0 warnings)**
3. `cargo test -p fnx-classes -p fnx-views -p fnx-dispatch -p fnx-convert -p fnx-algorithms -p fnx-generators -p fnx-readwrite -p fnx-durability -p fnx-runtime` via RCH: **PASSED (1,208+ tests passed, 0 failures)**
4. `.venv/bin/python scripts/verify_docs.py`: **PASSED (22 docs verified, 4 examples verified)**
5. Guarded pytest runner (`run_pytest_guarded.sh`): **PASSED (197 passed, 1 skipped, 0 failures)**

---

# Dependency Refresh: 2026-11-26

**Base:** main at fe463ffd9 · **Toolchain:** nightly-2026-08-31 (`rust-toolchain.toml`) · **Builds and tests:** remote workers via rch; Python on a Linux worker.

## Rust: semver-compatible `cargo update` (Cargo.lock)

| Crate | From | To | Reached through |
|---|---|---|---|
| `ahash` | 0.8.12 | 0.8.14 | optional ftui chain only |
| `zerocopy` / `zerocopy-derive` | 0.8.64 | 0.8.66 | dev, bench and optional chains only |
| `anyhow` | 1.0.104 | 1.0.105 | optional asupersync chain (`prost-derive`) |
| `clap` / `clap_builder` | 4.6.9 / 4.6.7 | 4.6.10 | criterion (bench) |
| `crc32fast` | 1.5.5 | 1.5.6 | optional asupersync chain |
| `sha2` (0.11 line) | 0.11.1 | 0.11.2 | optional asupersync chain (the workspace's own `sha2` stays 0.10.9) |
| `toml_edit` / `toml_parser` | 0.25.20 / 1.1.6 | 0.25.21 / 1.1.7 | lock only (`proc-macro-crate`); no workspace feature set builds it |

None of these reaches a default build, the wheel or the CLI. For each crate, `cargo tree --target all -e normal,build -i <crate> --workspace` with default features prints nothing. fuzz/Cargo.lock is unchanged.

**Gates:**
- `cargo clippy --workspace --all-targets --locked -- -D warnings`: clean.
- `cargo test --workspace --exclude fnx-python --no-fail-fast --locked`: 1952 passed, 1 failed, 246 ignored. The one failure, `doc_pass00_gap_matrix_gate`, predates this work (see below).
- `cargo audit`, root and fuzz locks, before and after: 0 vulnerabilities, 0 warnings.

### Held: `hashbrown` 0.17.1 (0.17.2 available)

hashbrown is the table behind `indexmap` in fnx-classes and fnx-algorithms, which is the graph-storage hot path. It was the only crate in the refresh on a default runtime path.

I ran a paired, alternating criterion A/B: `fnx-algorithms` `algorithm_benchmarks`, 36 benchmarks, 3 rounds per side. Both sides were built from the same commit and differed only in Cargo.lock. Every run was on one 4-slot worker, with each run taking all 4 slots.
- Overall the difference was noise: geometric mean new/old 1.011, median ratio 1.009.
- One benchmark regressed beyond the ~3% bar in all three rounds. `shortest_path_weighted/complete/100` went from 306-310 µs to 333-338 µs, **+9.5%**.
- Two more were slower in all three rounds, with median increases of +5.3% for `shortest_path_unweighted/complete/20` and +4.6% for `common_neighbors/overlap_rows/l32_r512_c32`.

Held for that reason. The 0.17.2 changes look internal: `std::hash::RandomState`, an allocator-leak fix for empty tables, wrapping `ProbeSeq` arithmetic, and lint and import cleanups. So the cause may be code layout rather than the table itself. Re-measure before taking it, or wait for 0.17.3.

## Held majors

- **`pyo3` 0.29.3 in fnx-python and fnx-conformance (0.30.1 available).** Held for a dedicated port with a Python-side A/B.
  - 0.30 drops the default `FromPyObject` derive for `#[pyclass]` and the blanket `PyClass + Clone` impl, moves `PyMutex`, and changes `#[pymodule_init]`.
  - fnx-python has 44 `#[pyclass]` items in 6 files, and its source was being edited on main while this ran.
  - This is the PyO3 boundary hot path, so its A/B needs two extension builds plus the Python benches.
  - `pyo3-log` 0.13.5 already accepts `<0.31`, so it is no longer the blocker.
- **`quick-xml` 0.41.0 in fnx-readwrite (0.42.0 available).** Held. 0.42 changes attribute keys and values from bytes to `&str`/`Cow<str>`. Earlier trials hit about 41 compile errors in the fnx-readwrite parsers, which are a parser hot path.
- **`sha2` 0.10.9 in fnx-runtime, plus dev-dependencies in fnx-algorithms and fnx-python (0.11.2 available).** Held.
  - 0.11's digests are hybrid-array outputs with no `LowerHex`, so every `format!("{:x}", digest)` site needs a helper. That is 15 files, 13 of them in fnx-python, which is under active edit.
  - This is evidence hashing, not a graph hot path, and nothing security-related forces it.
- **`networkx` oracle stays at 3.6.1 (3.4.2 on Python 3.10).** Moving to 3.7 is a separate qualification; see GitHub issue #5.

## Pre-existing gate failure (not caused by any change here)

`fnx-conformance` `doc_pass00_gap_matrix_gate` fails on main.
- Four commits on 2026-11-25 edited `docs/planning/EXISTING_NETWORKX_STRUCTURE.md` after `artifacts/docs/v1/doc_pass00_gap_matrix_v1.json` was last regenerated on 2026-11-21.
- The test compares only those two files, through serde_json, which no update here touches.
- The fix is to regenerate the matrix.
