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
