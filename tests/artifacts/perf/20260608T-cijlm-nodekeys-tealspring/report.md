# br-r37-c1-cijlm - Directed Native Node Keys

## Target

Profile-backed bead: `set(graph)` / `set(G)` callers pay per-node PyO3 iteration overhead. The sharpest live target is `non_neighbors` on directed multigraphs, where the directed classes lacked `_native_node_keys`, so the existing Python fast path could not avoid `set(graph.adj)` and adjacency row materialization.

Baseline target:

- Direct `DiGraph non_neighbors`: `0.014315485954284668s` vs NetworkX `0.003501579980365932s` (`4.09x` slower).
- Direct `MultiDiGraph non_neighbors`: `0.6395230169873685s` vs NetworkX `0.0037093739956617355s` (`172.41x` slower).
- Hyperfine `MultiDiGraph`: `1.06708416944s` mean, `1.0468087692399999s` median.
- cProfile: `non_neighbors` took `0.925s` / 64 calls; `_atlas` materialization took `0.888s`, with `__getitem__` / iterator row construction dominating.

## Lever

Expose `_native_node_keys` on `PyDiGraph` and `PyMultiDiGraph`, matching the existing undirected implementation:

- iterates `inner.nodes_ordered()`;
- maps each canonical node through `py_node_key`;
- returns display node objects in insertion order in one PyO3 crossing.

This is deliberately one lever. The existing `non_neighbors` wrapper already checks for `_native_node_keys`; no Python algorithm rewrite was needed.

## Results

- Direct `DiGraph`: `0.014315485954284668s -> 0.00906043709255755s` (`1.58x`).
- Direct `MultiDiGraph`: `0.6395230169873685s -> 0.00877087702974677s` (`72.91x`).
- Direct `MultiDiGraph` vs NetworkX ratio: `172.41x -> 2.51x`.
- Hyperfine `MultiDiGraph`: `1.06708416944s -> 0.31710568264s` (`3.37x`).
- After cProfile: `non_neighbors` is `0.007s` / 64 calls; `_native_node_keys` is `0.004s`; the adjacency materialization path drops out.

## Isomorphism Proof

- Baseline proof exact equality: `true`.
- After proof exact equality: `true`.
- Golden SHA unchanged: `a9b99d16a4eab0280a5e440c0bc0ad1edb1e2d41401f6b801fb5cf6db92e6240`.
- Ordering / tie-breaking: `_native_node_keys` follows `nodes_ordered()`, the same insertion order used by `__iter__`; `set(native_keys())` is constructed from the same ordered display objects as baseline `set(graph)` / `set(graph.adj)`.
- Floating point: no floating-point operations.
- RNG: no randomness.

## Validation

- Baseline `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- Touched-file format: `rustfmt --edition 2024 --check crates/fnx-python/src/digraph.rs`: passed.
- Broad `cargo fmt -p fnx-python --check`: blocked by pre-existing formatting drift in `crates/fnx-python/src/algorithms.rs` and `crates/fnx-python/src/readwrite.rs`; touched file passes.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- Candidate `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- Focused non-neighbor parity: `22 passed, 871 deselected`.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed.
- `git diff --check`: passed.
- UBS on `crates/fnx-python/src/digraph.rs`, the harness, and this report: exited `0`; no critical issues, with broad pre-existing warning inventory in `digraph.rs`.

## Score

- Impact: `5.0` (profile-backed `MultiDiGraph` target `72.91x` direct, `3.37x` hyperfine).
- Confidence: `4.0` (exact SHA unchanged, focused parity, crate check, release build, clippy, UBS exit `0`).
- Effort: `1.5` (two symmetric binding methods; no Python rewrite).
- Score: `13.33`.

Verdict: kept.

Next profile route: the remaining `2.51x` direct gap is no longer adjacency materialization. Attack a deeper primitive next: native `non_neighbors` set-difference/list emission or a bulk integer-node display path for lazy integer range graphs, rather than more `set(graph)` call-site shims.
