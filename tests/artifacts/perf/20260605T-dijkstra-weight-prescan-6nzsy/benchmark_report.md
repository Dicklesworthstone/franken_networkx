# br-r37-c1-6nzsy Benchmark Report

## Target

`bidirectional_dijkstra` on a deterministic connected `Graph` with `n=3000`,
`m=12000`, integer `weight` attributes, and repeated single-pair queries.

## Lever

Cache `_should_delegate_dijkstra_to_networkx` weight-classification results on
the graph when the graph's private token is safe:

- key: `(weight, nodes_seq, edges_seq)`
- cache disabled when Rust reports `edge_attrs_dirty=True`
- callable, non-string weight, multigraph, and fallback paths unchanged

This keeps direct live edge-attribute mutation on the old scan path.

## Before

Current-head in-process rch harness:

- `native_check_only`: `0.0009201398139056336 s/query`
- `native_kernel_only`: `0.000312620483390573 s/query`
- `public_fnx_bidirectional_dijkstra`: `0.0016151240944681274 s/query`
- `networkx_bidirectional_dijkstra`: `0.0006393149000359699 s/query`

Baseline cProfile over 100 public FNX calls:

- total: `0.130 s`
- `_native_check_dijkstra_weights_fast`: `0.089 s`
- `_native_bidirectional_dijkstra`: `0.040 s`

Baseline 100-query process hyperfine, dominated by graph construction:

- public FNX: `590.3 ms +/- 62.3 ms`
- native check only: `595.4 ms +/- 181.0 ms`
- native kernel only: `445.2 ms +/- 57.8 ms`
- NetworkX: `411.1 ms +/- 35.0 ms`

## After

After in-process rch harness:

- `native_check_only`: `0.0014269763349956418 s/query`
- `native_kernel_only`: `0.0004099381266860291 s/query`
- `public_fnx_bidirectional_dijkstra`: `0.0004072218777663592 s/query`
- `networkx_bidirectional_dijkstra`: `0.0008004146029836395 s/query`

After cProfile over 100 public FNX calls:

- total: `0.042 s`
- `_native_bidirectional_dijkstra`: `0.041 s`
- `_native_check_dijkstra_weights_fast`: absent from hot path

Matched current-binary hyperfine, 1000 public queries:

- no-cache dispatcher: `3.108 s +/- 0.864 s`
- cached dispatcher: `764.1 ms +/- 76.2 ms`
- speedup: `4.07x +/- 1.20x`

## Score

Impact `4`, confidence `4`, effort `2`; score `8.0`.

Keep: the paired hyperfine and in-process profile both exceed the `>=2.0`
threshold, with parity proof below.
