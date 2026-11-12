# add_nodes_int lazy display-key substrate

Bead: `br-r37-c1-17ucl`

## Profile target

`Graph.add_nodes_from(range(100000))` was still dominated by the native
`_fast_add_int_nodes_range_stop` method after earlier loop tweaks were rejected.
The fresh rch cProfile baseline spent `0.828s / 1.080s` across 7 calls in that
method.

## Lever

For the range fast path, `PyGraph` now records consecutive integer display keys
as an implicit `0..stop` range instead of materializing one Python int object in
`node_key_map` per node. `py_node_key` synthesizes Python ints on read, and
later mutation/copy/subgraph paths materialize explicit keys only when needed.

This is a single structural lever: remove the per-node Python-object side-table
tax for generated integer ranges.

## Benchmarks

All benchmarks were run through `rch`.

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Direct FNX mean, 9 repeats | `0.12318082067779162s` | `0.03410787522120194s` | `3.61x faster` |
| Direct NetworkX same run | `0.06042217222016512s` | `0.04189929677199365s` | control |
| FNX/NX ratio | `2.038669186353443` | `0.8140440973701578` | FNX moved from slower to faster |
| cProfile FNX mean, 7 repeats | `0.1332626897076677s` | `0.035910729285595674s` | `3.71x faster` |
| Native method cProfile total | `0.828s / 7 calls` | `0.210s / 7 calls` | `3.94x faster` |
| Hyperfine FNX process mean | `0.91825847524s` | `0.69890363868s` | `1.31x faster` |
| Hyperfine NetworkX process mean | `0.9558827175400001s` | `0.7341453359800001s` | control |

Golden construction digest stayed unchanged:

`eae2ed4eadc93d3264aef2fb5cd05bce54b2c934b5805383f8e5ad4113505b75`

## Score

Impact `4` x Confidence `5` / Effort `2` = `10.0`.

Keep.
