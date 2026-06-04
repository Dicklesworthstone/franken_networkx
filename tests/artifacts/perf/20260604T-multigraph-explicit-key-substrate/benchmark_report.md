# MultiGraph Explicit-Key Metadata Substrate

Bead: `br-r37-c1-04z53.45`

## Profile Target

Baseline profile showed `MultiGraph.add_edge(i, i + 1, key=...)` dominated by
`PyMultiGraph._fast_add_explicit_{int,str}_edge` on fresh endpoint pairs.

## Lever

For the fresh explicit-key fast path, replace the metadata `entry(...).or_insert`
and `remember_edge_key_object(...)` sequence with direct metadata inserts. The
fast path has already proven the endpoint pair has no edge, so the metadata key
cannot be a first-wins collision.

## Benchmarks

Construction sweep, `rch exec`, release extension:

| Case | Baseline FNX mean | Final FNX mean | Speedup | Golden |
| --- | ---: | ---: | ---: | --- |
| `multigraph_int_keys` | 1.025135194s | 0.229993594s | 4.46x | match |
| `multigraph_str_keys` | 0.970576645s | 0.213254650s | 4.55x | match |

Comparable hyperfine shape for `multigraph_str_keys`, 7 benchmark repeats per
run:

| Baseline | Final | Speedup |
| ---: | ---: | ---: |
| 8.670788025s | 2.218691239s | 3.91x |

Score: `Impact 4.5 x Confidence 0.9 / Effort 1.0 = 4.05`, keep.

## Isomorphism Proof

Ordering/tie-breaking: the golden digest serializes `graph.nodes()` and
`graph.edges(keys=True, data=True)` in iteration order, including the Python type
and representation of nodes and explicit keys. FNX and NetworkX digests match
for both int-key and string-key cases.

Floating point and RNG: not present in this construction workload.

Golden SHA:

- Previous before/after compact string-key golden:
  `56836068fa77949b6a20e95ae0987b0c28d04d197c1c20d2e6480f85a7d9d9b3`
- Final current compact int-key + string-key golden:
  `fca194c06ff859a53e38954614f8af5e5fdc36dc9081e9d24a0162638791c16d`

## Validation

- `cargo fmt --check -p fnx-python`
- `rch exec -- cargo check -p fnx-python --all-targets`
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_to_undirected_parity.py -q`
- `ubs crates/fnx-python/src/lib.rs`
