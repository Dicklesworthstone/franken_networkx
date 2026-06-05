# perf: batch operator/relabel per-edge loops + native union(rename) (br-r37-c1-kmxke)

## Problem
disjoint_union 7.08x / union(rename) 6.37x / relabel_nodes ~3.3x vs nx:
- union_all's simple branch did a Python add_edge per edge; its
  multigraph branch called add_edges_from with a SINGLETON list per edge
- relabel_nodes' copy path did a Python add_edge per edge
- union(rename=...) round-tripped through nx entirely
  (_union_with_rename_via_parity: 2x fnx->nx conversion + nx.union +
  per-edge _from_nx_graph rebuild) although fnx's union_all natively
  supports rename (nx's union IS union_all([G, H], rename))
15982 Python add_edge calls per disjoint_union(1500+800) build.

## Lever (one)
Batch all three through ONE add_edges_from each; route union(rename)
to union_all. Node-merging relabels collapse multiple old edges onto
one pair — the batch path merges attrs in iteration order, identical
to the per-edge sequence. Union node sets are disjoint (validated
before edges), so no cross-graph merges.

## Proof
- 0 failures: 4 classes x str/int keys x rename forms ((), 2-tuple,
  single-prefix) for union; disjoint_union all classes; relabel full +
  node-MERGING maps; union collision error type+message exact
  GOLDEN_CORPUS_SHA256: c2864e9b5f39b11676a9cf1a757b7cf4e3665b12f3256b7da3b045249ea0dd89
- tests/python/test_operator_batch_parity.py: 31 passed
- full tests/python suite: 21409 passed; 6 failures identical to HEAD

## Bench (interleaved warm min-of-8, n=1500+800 weighted)
- disjoint_union: 104.7 -> 63.2ms; 7.08x -> 4.13x
- union(rename):   99.3 -> 37.4ms; 6.37x -> 2.33x
- relabel_nodes:        -> 22.2ms; 3.78x (was per-edge-bound)
- residual = add_edges_from batch substrate (w1dm8) +
  convert_node_labels_to_integers chain in disjoint_union

## Validation
- Python-only change; built/tested in isolated worktree at e8953817e
