# Benchmark Report

## Bead

`br-r37-c1-04z53.39`

## Workload

Deterministic sparse simple `Graph` with 3000 nodes, block size 10, and 9000
random extra edges. The call under test is default `quotient_graph(G,
partition)` with default node data, default edge relation, and default
`weight="weight"`.

Harness: `bench_quotient_graph.py`.

## Baseline

- Direct FNX sample: `6.852903510996839s`
- Direct NetworkX sample: `2.1847441050049383s`
- Hyperfine FNX process envelope: `7.33879451944s +/- 0.12399965320295445s`
- Digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

Baseline cProfile showed repeated filtered-view counting:

- `_default_node_data`: `8.809s`
- filtered `number_of_edges`: `12.083s`
- filtered `number_of_nodes`: `5.552s`
- `density`: `4.383s`
- `_node_visible`: `13.719s`
- `_from_nx_graph`: `4.872s`

## Lever

Build partition-local sufficient statistics once:

- `block_index`: node to block index.
- `block_nnodes`: block sizes.
- `block_nedges`: internal edge counts from one source-edge scan.
- `default_pair_totals`: default simple-undirected cross-block weight totals
  from the same edge scan.

Default node attrs are inserted directly in NetworkX key order. The `graph`
attribute remains `G.subgraph(block)`. When `create_using is None`, the function
returns the directly constructed fnx result instead of copying it through
`_from_nx_graph`.

## After

- Direct FNX sample: `0.09430924800108187s`
- Direct NetworkX sample: `2.221488392999163s`
- Direct FNX speedup: `72.66417298670673x`
- Hyperfine FNX process envelope: `0.46055709352s +/- 0.019383029721207087s`
- Hyperfine speedup: `15.93460316363862x`
- Digest: `3b82f51eccda8bd9a2f0a24657abf67f8bb2bc9b9da8e49d136f6089b31be62a`

After cProfile moved the workload to quotient edge insertion and result digest
materialization:

- `quotient_graph`: `0.117s`
- `_add_default_undirected_bucketed_edges`: `0.074s`
- `_default_node_data`: `0.010s`
- `subgraph`: `0.009s`

## Verdict

PRODUCTIVE. Keep.

Opportunity score: Impact 5 x Confidence 5 / Effort 2 = 12.5.
