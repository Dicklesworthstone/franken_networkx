# br-r37-c1-04z53.74

## Target

`random_regular_graph(8, 1500, seed=12345)` on the default `Graph` path.

Baseline artifacts are in `tests/artifacts/perf/20260611T-random-regular-residual-blackthrush/` from the immediately preceding rejected-lever pass.

- Direct FNX median: `0.0075949641s`
- Direct FNX mean: `0.0098278818s`
- RCH hyperfine FNX mean: `0.8730308469s`
- RCH hyperfine NetworkX mean: `0.9390319024s`
- Baseline profile over 160 FNX calls: `2.266s`, with `_try_creation` `1.489s`, Python `random.shuffle` `1.130s`, and final `add_edges_from` `0.681s`

## Lever

Replace only the default-path Python `_try_creation` pairing loop with a native state machine that returns a CPython `set` of `(u, v)` integer tuples.

The final `Graph.add_edges_from(edges)` call remains unchanged. This preserves graph mutation, node order, adjacency order, and edge-view behavior through the existing proven Python graph-insertion path.

The fast path is guarded to exact default graph construction with exact integer `d`, `n`, and non-bool integer seed in `u64`, plus a bounded stub tape. Unsupported seed objects, global RNG state, custom `create_using`, and oversized inputs fall back to the prior Python implementation.

## Isomorphism Proof

Golden target proof:

- `all_match`: `true`
- FNX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- NetworkX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- Nodes: `1500`
- Edges: `6000`

Broad generator proof also passed for all scenarios in the harness, including the previous `circular_ladder_graph(2000)` digest `e3c71666e1894596d6a3e8949cafe6bb4fb192776696d48dfe08b2218dc9dcba`.

Ordering is preserved by matching NetworkX stub initialization (`list(range(n)) * d`), Fisher-Yates shuffle using the existing Python-compatible MT19937 helper, insertion-ordered `potential_edges`, and CPython set materialization in the same edge-add sequence. Tie-breaking is the same `(min, max)` endpoint canonicalization. There is no floating-point surface. RNG parity is restricted to exact integer seeds covered by the fast-path guard; other RNG surfaces fall back.

## Rebench

- Direct FNX median improved `0.0075949641s -> 0.0056838205s` (`1.34x`)
- Direct FNX mean improved `0.0098278818s -> 0.0064391764s` (`1.53x`)
- RCH hyperfine FNX mean improved `0.8730308469s -> 0.6896976485s` (`1.27x`)
- RCH hyperfine NetworkX control after mean: `0.9143708338s`
- FNX moved from `1.08x` faster than NetworkX in the baseline envelope to `1.33x` faster after
- cProfile over 160 FNX calls improved `2.266s -> 0.946s` (`2.39x`)
- Native `random_regular_edges_pyset` costs `0.126s`; remaining dominant cost is final `add_edges_from` / `_try_add_edges_from_batch` at `0.662s` / `0.494s`

Score: `4.5` (`Impact 3.0 * Confidence 3.0 / Effort 2.0`). Kept.

## Gates

- `maturin develop --release --features pyo3/abi3-py310` via RCH: passed
- `pytest tests/python/test_classic_generators.py tests/python/test_degree_sequence_generators_conformance.py -q -k 'random_regular or native_random_generators_do_not_fallback'`: `23 passed`
- `cargo test -p fnx-generators random_regular_python_edge_insertion_order_matches_fixture --lib` via RCH: passed
- `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` via RCH: passed with pre-existing warnings
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` via RCH passed with allowances for pre-existing duplicated/unused attributes plus existing local warning families
- `rustfmt --edition 2024 --check crates/fnx-generators/src/lib.rs crates/fnx-python/src/generators.rs`: passed
- `python -m py_compile python/franken_networkx/__init__.py`: passed
- `git diff --check`: passed

## Next Target

Reprofile after push. The current random-regular residual is final graph insertion: `add_edges_from` / `_try_add_edges_from_batch` dominates after the pairing state machine. The next deeper primitive should be a direct graph builder that can prove the same CPython set-order adjacency payload, including adversarial hash-equal node certificates, instead of trying `_fast_add_int_edges` again.
