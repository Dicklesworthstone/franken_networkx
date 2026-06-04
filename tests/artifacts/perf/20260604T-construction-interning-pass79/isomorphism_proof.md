# br-r37-c1-nxgph Isomorphism Proof

## Change

Add a narrow fast path for exact `MultiGraph.add_edge(u, v, key=k)` calls where:

- `type(self) is MultiGraph`
- `type(u) is int`
- `type(v) is int`
- `type(k) is int`
- no edge attributes are supplied
- the endpoint pair has no existing parallel-edge bucket

All other cases fall back to the previous public wrapper and Rust binding.

## Observable Behavior

- Ordering preserved: yes. The fast path inserts nodes in the same endpoint encounter order as the generic path and inserts the edge into the same adjacency orientation used by `MultiGraph`.
- Tie-breaking unchanged: yes. The fast path is only used when the endpoint pair is fresh, so there is no existing-key conflict to resolve. Repeated pairs fall back to the old key-resolution path.
- Edge key display unchanged: yes. The Rust internal key remains `0` for a fresh pair, and `edge_py_keys` records the caller's explicit Python key object, matching the previous generic path.
- Hash-equivalent lookup unchanged: yes. Existing-pair and lookup paths still use `resolve_internal_edge_key`, so `key=7.0` resolves to an edge first inserted with `key=7`.
- Attribute semantics unchanged: yes. Attribute-bearing calls are excluded from the fast path and use the previous mutation path.
- Node object visibility unchanged: yes for the exact fast path. The first Python int object for a canonical integer node remains stored in `node_key_map`; existing hash-equivalent or non-int forms fall back.
- Floating-point behavior: N/A. No floating-point arithmetic is introduced.
- RNG behavior: N/A. No random state is touched.

## Golden Outputs

- Baseline FNX digest: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`
- NetworkX digest: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`
- After FNX digest: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`

## Regression Test

Focused parity coverage:

```text
RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_attribute_access_parity.py -q -k 'explicit_int_key or non_integer_multigraph_edge_keys'
```

Result: `3 passed, 137 deselected`.

## Verification Commands

- `cargo fmt -p fnx-classes --check`
- `cargo fmt -p fnx-python --check`
- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `sha256sum -c artifact_sha256.txt`
