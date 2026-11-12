# Validation Summary

Bead: `br-r37-c1-acuub`

## Build and Lint

- `RCH_ENV_ALLOWLIST=VIRTUAL_ENV,PATH rch exec -- cargo fmt --package fnx-python --check`: passed.
- `RCH_ENV_ALLOWLIST=VIRTUAL_ENV,PATH rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `RCH_ENV_ALLOWLIST=VIRTUAL_ENV,PATH rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `.venv/bin/python -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-digraph-edges-native-order/bench_digraph_edges.py`: passed.

## Python Behavior Checks

Focused Python parity passed for:

- Empty DiGraph.
- Singleton DiGraph.
- Deterministic directed graphs with 20, 180, and 900 edges.
- `list(G.edges())` order against NetworkX.
- `list(G.edges(data=True))` order and attributes against NetworkX.
- Live edge view created before mutation and iterated after mutation.
- `type(G.edges()).__name__` against NetworkX.

## UBS

- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; no critical findings, existing broad file warnings only.
- `ubs tests/artifacts/perf/20260603T-digraph-edges-native-order/bench_digraph_edges.py`: exit 0; no warnings.
- `ubs python/franken_networkx/__init__.py`: stopped after exceeding 60 seconds with no scan output beyond startup; this large generated file has timed out in prior runs. Focused `py_compile` and behavior parity checks passed.

## Golden

`golden_before.json` and `golden_after.json` are identical:

```text
837ade831910ce92b5d7c457d17182faf106639046543d061cf3ec16424fbd5f
```
