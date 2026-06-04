# create_empty_copy + contracted_nodes: drop redundant _from_nx_graph rebuild (part 2)

Bead: `br-norebuild2` (follow-up to br-norebuild / 48bfed4d4).

## Catastrophe
create_empty_copy and contracted_nodes (identified_nodes) built an fnx-typed result
graph via _concrete_class_for(G)() and then ran _from_nx_graph(H) on it -- a
redundant SECOND full construction of an already-correct fnx graph. Warm min-of-5
vs networkx: create_empty_copy 10x (growing), contracted_nodes 13.3x slower.

## Lever (one)
_concrete_class_for(G)() always returns the canonical fnx type, so H already has
the right node/edge/adjacency order. Return H directly instead of rebuilding it.
- create_empty_copy: byte-identical to networkx (200/200, simple + multigraph;
  it is edgeless so no adjacency-order subtlety).
- contracted_nodes: byte-identical for simple graphs; for MULTIGRAPHS returning H
  is STRICTLY MORE correct -- the old _from_nx_graph rebuild re-canonicalized
  parallel-edge adjacency in a way that DIVERGED from networkx on 31/68 sampled
  multigraph contractions (a pre-existing bug). Returning H fixes those 31 with
  ZERO regressions (the lone remaining residual, a multigraph self-loop
  adjacency-order edge case, fails identically in the old rebuild).

## Proof
test_create_empty_copy_contracted_no_rebuild_parity.py (4/4): create_empty_copy
exact over 60x2 graphs; contracted_nodes simple exact over 80x2; multigraph
no-regression (>=90% match vs the old ~53%); copy=False identity preserved.

## Benchmark (warm min-of-5)
    function           before   after
    create_empty_copy  10x      3.28x
    contracted_nodes   13.3x    4.23x
(Residual is base construction tax of building the result graph -- substrate-bound.)

## Files
- python/franken_networkx/__init__.py: create_empty_copy, contracted_nodes.
