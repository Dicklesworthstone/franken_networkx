# br-r37-c1-2gcnp Isomorphism Proof

## Change
- Route exact `Graph.add_nodes_from(range(0, stop, 1))` through `_fast_add_int_nodes_range_stop` again.
- Make `GraphRef::py_node_key` delegate exact `Graph` result materialization through `PyGraph::py_node_key`, so sparse lazy integer nodes display as Python `int` keys in native algorithm outputs.

## Baseline/Profile
- Direct baseline: FNX mean `0.23725605084161674s`; NetworkX mean `0.03391759000286194s`; ratio `6.995073966682105`.
- Hyperfine baseline: FNX `621.0 ms +/- 151.0 ms`; NetworkX `196.4 ms +/- 10.2 ms`.
- Baseline profile: `Graph.add_node` `0.903s / 5` builds; Python `add_nodes_from` `1.271s / 5` builds.

## After
- Direct after: FNX mean `0.038051405148248056s`; NetworkX mean `0.0379051511491915s`; ratio `1.003858420151945`.
- Hyperfine after: FNX `321.9 ms +/- 23.9 ms`; NetworkX `206.8 ms +/- 17.9 ms`.
- After profile: native `_fast_add_int_nodes_range_stop` `0.141s / 5` builds.

## Behavior Proof
- Ordering preserved: yes. The native range path inserts canonical nodes in ascending range order, matching `range(0, stop, 1)`.
- Tie-breaking unchanged: yes. Only Python-key materialization changes for exact `Graph` algorithm result dicts; algorithm traversal order remains the existing Rust graph order.
- First object per canonical key preserved: yes. Lazy range nodes display as Python ints through `PyGraph::py_node_key`; later hash-equal float/bool aliases still do not replace the first visible int key.
- Duplicate handling preserved: yes. `extend_nodes_unrecorded` preserves existing nodes; the Python route remains limited to exact zero-start unit-step ranges without attrs.
- Attr behavior preserved: yes. Attr-bearing `add_nodes_from` calls still use the generic path.
- Floating-point behavior: N/A. No numeric algorithm arithmetic changed.
- RNG behavior: N/A. No random state touched.
- Golden output: semantic SHA `fed90eced5fdcd2b17537cb14d620ce6aed16d1e0f399c96f79d39f5068a314f` unchanged.
- Failure probe: private lazy path plus `triangles`, `clustering`, `neighbors`, `G[0]`, copy, subgraph, edge_subgraph, and all-pairs shortest path matches NetworkX; after-probe SHA `ebbe517d699118a8f540aed3a82cedf4ddcbddeb4957886512c5d1b624bee1d1`.

## Score
- Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.

## Alien Primitive
- Lazy materialization / sparse key map with canonical int range witness.
- Graveyard mapping: data-structure allocation-churn reduction and lazy materialization guard; not another branch micro-tweak.
