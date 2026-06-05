# perf: lazy attr-mirror dicts, w1dm8 substrate phase 1 (br-r37-c1-89kxg)

## Problem
Every PyGraph construction path eagerly allocated an EMPTY PyDict
mirror per node and per edge (~6700 allocs for a 1500-node/5217-edge
build) — pure dual-representation overhead, since every reader already
goes through materialize_*/ensure_*/entry().or_insert and treats
absence as empty attrs.

## Lever (one)
Remove eager empty-mirror allocation from the three PyGraph
construction paths: add_plain_edge_batch (the whole mirror loop),
add_attr_edge_batch (node mirrors + attr-less edges; attributed edges
still materialize with content), add_edge (node mirrors + attr-less
edge mirror). Inner Rust attrs stay EAGER (the g5ifq weighted-kernel
hazard does not apply — only the Python mirror of EMPTY dicts is
deferred). Mirrors materialize on first observation, preserving dict
identity (`G[u][v] is G[u][v]`, symmetric live sharing).

## Bench (interleaved warm min-of-12, n=1500/E=5217)
- add_edges_from plain: 6.62 -> 4.83ms; 2.88x -> 2.10x
- add_edges_from attrs: 8.86 -> 7.36ms; 3.41x -> 2.74x
- downstream: from_dict_of_dicts 2.85x -> 2.56x, Graph(G) ~2.09x
- follow-up (bead): same treatment for DiGraph/Multi classes and the
  read_adjlist/read_edgelist kernels (still eager)

## Proof
- pr8q6 90-case + nlanb 51-case differentials: 0 failures
- identity/mutation contracts: dict identity across observations,
  symmetric live sharing, copy/copy.copy/deepcopy/pickle round-trips,
  post-construction mutation + dijkstra exactness
- 5 committed tests (test_lazy_mirror_parity.py)
- full pytest on the candidate tree: 21485 passed; 6 failures
  identical to HEAD (pre-existing)
