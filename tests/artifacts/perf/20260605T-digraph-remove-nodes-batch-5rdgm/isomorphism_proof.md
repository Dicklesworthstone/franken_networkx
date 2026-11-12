# br-r37-c1-5rdgm Isomorphism Proof

## Target

`DiGraph.remove_nodes_from(nodes)` now batches Rust storage compaction for present
victim nodes instead of calling `DiGraph::remove_node` once per item. The Python
wrapper still materializes the iterable before the raw PyO3 call, preserving the
existing NetworkX-compatible generator/error boundary.

## Observable State

- Node membership: the batch path filters the same present canonical node set as
  repeated removal. Duplicate victims and missing victims are no-ops, as in
  NetworkX and the prior implementation.
- Node order: `IndexMap::retain` preserves the relative order of every survivor.
  Removing a set of victims one at a time also leaves survivors in the same
  relative order.
- Edge membership: an edge is removed iff its source or target is in the victim
  set. This is exactly the incident-edge union removed by the repeated
  `remove_node` path.
- Edge order: public directed edge iteration uses node order followed by
  successor-row order. The batch path retains survivor successor rows and row
  entries in place, so tie-breaking/order is unchanged.
- Node and edge attributes: surviving node attrs and edge attrs are not copied or
  rewritten; removed node attrs and incident edge attrs are dropped. The
  generated golden records compare ordered nodes with attrs and ordered edges
  with attrs against NetworkX.
- Directed row-key overrides: `succ_py_keys` and `pred_py_keys` drop every row
  override touching a removed endpoint, matching the old per-node cleanup.
- Cache invalidation: node sequence is bumped once after a materialized removal
  call, as before. Edge sequence is bumped when an incident edge or edge-attr
  record is removed.

## Non-Surfaces

- Floating point: not used by this mutation path.
- RNG: not used by this mutation path.
- Algorithmic tie-breaking: no traversal algorithm runs here; the only
  tie-break surface is public ordering, covered above.

## Golden Output

Harness:
`tests/artifacts/perf/20260605T-digraph-remove-nodes-batch-5rdgm/digraph_remove_nodes_batch_bench.py`

The golden pass compares FNX and NetworkX after `range`, `list`, and `tuple`
victim inputs over deterministic attributed directed graphs:

- Baseline internal golden SHA256: `536bb003276301015c74aa917da27bbb466a798b18b775b761a4a6a766bf34e1`
- After internal golden SHA256: `536bb003276301015c74aa917da27bbb466a798b18b775b761a4a6a766bf34e1`
- Baseline golden file SHA256: `4b947e1dae2f460e97930d236eb5f919e60172911303441b8594841637fe0ba8`
- After golden file SHA256: `4b947e1dae2f460e97930d236eb5f919e60172911303441b8594841637fe0ba8`

The sparse target direct benchmark also produced identical post-mutation digests:
`4818dcc69e640d7feb05c03f12887564b0f77e237910b1d4cdfd613eaffdbefd`.
