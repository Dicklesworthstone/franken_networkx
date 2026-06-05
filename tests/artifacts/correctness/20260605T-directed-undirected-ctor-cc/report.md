# fix: directed->undirected cross-class ctor parity (br-r37-c1-bt8m4)

## Bug

Collapsing a directed source into an undirected target, nx's
from_dict_of_dicts walks adjacency CELLS with a `seen` reverse-pair
skip: the FIRST direction encountered wins (keeping all its parallel
keys); the reverse direction is skipped ENTIRELY — attrs never merge
across directions. fnx's _copy_constructor_graph_source flat
add_edges_from let the reverse direction overwrite (last-wins):

  MultiGraph(DiGraph[a->b w1, b->a w2])      fnx w2, nx w1
  Graph(MultiDiGraph[...])                    same
  MultiGraph(MultiDiGraph[...])               same

18/96 matrix cases at HEAD (found by the ymeml ctor-matrix proof;
pre-existing, reproduced on HEAD-pure build).

## Fix (one lever)

Three new collapse branches in _copy_constructor_graph_source
(source_is_directed and not target_is_directed, non-expand):
group flat edges by (u, v) cell preserving first-encounter order, skip
any cell whose reverse pair was seen, keep all parallel keys of the
kept direction (Graph targets merge those keys in key order — nx's
per-key G[u][v].update). Self-loop cells keep all parallel keys
(grouping, not per-edge skip, replicates nx's cell-wise walk).
Undirected->undirected and expand paths untouched.

## Proof

- 96-case cross-class matrix (4x4x6 corpora): 18 failures -> 0.
  GOLDEN_CORPUS_SHA256:
  31e1d311ee79d1cba6585d0c9b99b410632a98d29c28cf620ccbcca10a594013
- adversarial shapes all match nx: reverse-direction-first input,
  parallel keys + reverse, parallel self-loops, single self-loop
- tests/python/test_cross_class_ctor_parity.py: 9 passed
- full tests/python suite: 21380 passed; 6 failures identical to HEAD
  (pre-existing, unrelated)
- Python-only change (no .so rebuild)
