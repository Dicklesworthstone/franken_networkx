# br-r37-c1-17ucl lazy integer range node keys

One lever: `Graph.add_nodes_from(range(0, n))` records `0..stop` as a compact
lazy integer display range instead of eagerly allocating/storing one Python int
object per canonical node. Boundaries that copy or convert a `PyGraph` now
materialize through `py_node_key` so the sparse display cache cannot drop nodes.

## Baseline

- Direct rch harness: `0.05008851731410967s`
- cProfile rch harness: `0.05518483257453356s`
- cProfile `_fast_add_int_nodes_range_stop`: `0.305s / 7 calls`
- Hyperfine command mean: `530.7 ms +/- 27.5 ms`
- Golden digest: `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

## After

- Direct rch harness: `0.0328498243739327s` (`1.52x`)
- cProfile rch harness: `0.043559101418525516s` (`1.27x`)
- cProfile `_fast_add_int_nodes_range_stop`: `0.279s / 7 calls`
- Hyperfine command mean: `485.4 ms +/- 46.7 ms` (`1.09x`)
- Golden digest: `eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

## Score

Impact 3 x Confidence 4 / Effort 3 = 4.0.

