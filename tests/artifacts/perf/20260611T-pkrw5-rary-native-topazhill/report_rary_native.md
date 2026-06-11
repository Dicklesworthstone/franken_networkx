# br-r37-c1-pkrw5 - native r-ary tree constructor

## Lever

Route exact built-in non-negative integer calls for `full_rary_tree(r, n)` and
`balanced_tree(r, h)` through a new `full_rary_tree_native` PyO3 helper.

The helper builds the NetworkX BFS edge stream directly into a lazy-int
`PyGraph`, avoiding the generic string-node generator report and Python
`add_edges_from` remapping path. Bools, int subclasses, negative arguments, and
`create_using` still use the existing Python/Rust fallback paths. Oversized
public calls also fall back to the existing raw bindings, preserving observed
public behavior.

## Profile Target

Baseline profiles showed the residual target inside the old raw bindings:

- `full_rary_tree(2, 8191)`: 10 samples spent 0.138 s in
  `_fnx.full_rary_tree`.
- `balanced_tree(2, 12)`: 10 samples spent 0.123 s in
  `_fnx.balanced_tree`.

Final profiles:

- `full_rary_tree(2, 8191)`: 10 samples spend 0.030 s in
  `_fnx.full_rary_tree_native`.
- `balanced_tree(2, 12)`: 10 samples spend 0.023 s in
  `_fnx.full_rary_tree_native`.

## Hyperfine Delta

Command shape: 100 graph constructions per run, 10 runs, warmup 2.

| Scenario | Baseline FNX mean | Final FNX mean | Self speedup | Final NX mean | Final FNX vs NX |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full_rary_tree(2, 8191)` | 1.742080478 s | 0.697742350 s | 2.50x | 1.558364173 s | 2.23x faster |
| `balanced_tree(2, 12)` | 1.779418935 s | 0.704538559 s | 2.53x | 1.585141165 s | 2.25x faster |

Direct Python timing medians:

- `full_rary_tree(2, 8191)`: 0.016102376 s -> 0.002946031 s, 5.47x.
- `balanced_tree(2, 12)`: 0.016391063 s -> 0.002919410 s, 5.61x.

Score: Impact 2.50 x Confidence 0.90 / Effort 1.0 = 2.25, accepted.

## Isomorphism And Golden Evidence

`candidate_proof_final.json` reports `all_match: true` across 9 generator
scenarios. The target graph digest is unchanged and matches NetworkX:

- `full_rary_tree(2, 8191)`: `c22a5febbe363b33eaad5df75b24b8c29435d05ce70f5f7eb281ec4d3e5bc6d4`
- `balanced_tree(2, 12)`: `c22a5febbe363b33eaad5df75b24b8c29435d05ce70f5f7eb281ec4d3e5bc6d4`

Targeted parity tests passed:

- `tests/python/test_rary_tree_deque_parity.py`
- `tests/python/test_review_mode_regression_lock.py::test_balanced_tree_negative_r_match_nx_geometric_formula`
- `tests/python/test_review_mode_regression_lock.py::test_full_rary_tree_negative_args_match_nx`

Manual oversized public behavior check matched NetworkX node/edge counts:

- `full_rary_tree(2, 100001)`: 100001 nodes, 100000 edges.
- `balanced_tree(2, 16)`: 131071 nodes, 131070 edges.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings -A clippy::collapsible_if`: passed.
- `maturin develop --release --features pyo3/abi3-py310`: passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/generators.rs`: passed.
- `cargo fmt -p fnx-python --check`: blocked by pre-existing formatting drift in unrelated `fnx-python` files.
- `ubs crates/fnx-python/src/generators.rs`: completed with 0 critical findings; warning/info inventory only.
- `ubs crates/fnx-python/src/generators.rs python/franken_networkx/__init__.py`: Rust scan completed, Python scan timed out after 180 s on the large wrapper.

Final evidence files use the `candidate_*_final*` names. Earlier
`candidate_*` files in this directory are retained as draft evidence from the
pre-cap-preservation candidate.
