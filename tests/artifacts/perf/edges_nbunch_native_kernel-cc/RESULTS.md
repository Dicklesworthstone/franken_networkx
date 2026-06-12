# edges(nbunch, data) — native partial-coverage kernel + native count for __len__

## Lever
The prior to_dict_of_dicts routing OVERBUILT the whole graph for a partial
nbunch, and `list(view)` materialized the tuple list TWICE (once for __len__'s
size hint, once for __iter__). Two native kernels:
- edges_nbunch_data: walks ONLY the nbunch rows in Rust (nx UndirectedEdgeView
  order + undirected dedup, self-loops kept), attaching the SAME live edge dict
  object nx yields (via edge_py_attrs) — no full-graph overbuild, no per-edge
  AtlasView/dict() copy. Raw kernel is 0.11ms vs nx 0.28ms (2.5x).
- edges_nbunch_count: pure-Rust edge count (no PyObject alloc) for __len__, so
  list()'s size-hint no longer triggers a second full materialize.

## Correctness
edges(nbunch,data) vs nx: 250 cases, 0 mismatches; golden 5dcd6a756e28e8a7
(UNCHANGED from the prior commit = byte-identical). len(edges(nbunch)) parity: 0
mismatches. data=True yields nx's LIVE edge dict. 1297 edges/edge-view/liveness/
mutation/dicsr-cache tests pass (no liveness regression).

## Benchmark (warm min, interleaved before/after vs prior commit) — ratio nx/fnx
| scenario                      | BEFORE (tdd)    | AFTER (native)  | self-speedup |
|-------------------------------|-----------------|-----------------|--------------|
| attrless edges(150,data=True) | 0.479ms (0.54x) | 0.267ms (0.96x) | 1.8x         |
| attr edges(150,data='weight') | 0.527ms (0.63x) | 0.308ms (1.07x) | 1.7x         |

attr-present flips to FASTER than nx (1.07x); attr-less reaches ~parity (0.96x).
From the original AtlasView walk (3.43ms) this is ~12x. Residual (~parity for
attrless) is the per-element fail-fast iterator guard, which is parity-bound
(nx checks concurrent-modification per element too).
