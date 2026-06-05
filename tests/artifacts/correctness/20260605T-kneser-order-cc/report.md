# fix: kneser_graph insertion-order parity (br-r37-c1-jv0h5)

## Bug
fnx built kneser via all-nodes-first add_nodes_from + pairwise
isdisjoint add_edge loop — same node/edge SETS as nx but different
insertion ORDER. nx's construction: node order is edge-DISCOVERY order
(`(s, t) for s in subsets for t in combinations(universe - set(s), k)`),
with nodes pre-added only when 2k > n (isolated nodes possible).
Found by the y7m24 proof; pre-existing (reproduced at HEAD).

## Fix (one lever)
Replicate nx's construction VERBATIM in the pure-Python wrapper —
including the CPython set-difference iteration the t-generation depends
on (Python-level, so set semantics match nx exactly; this is NOT
routable to Rust per the set-order parity rule).

## Proof
- 16-point (n,k) grid incl. 2k>n isolated-node shapes and k==n:
  full canon (node order, edge order, adjacency rows) == nx, 0 failures
  GOLDEN_CORPUS_SHA256: 38b9406234974330e819809a3604c8c4520183aaa8605a7143bd805c3e1fb18a
- error parity (n<=0, k<=0, k>n): type+message exact
- petersen identity (10 nodes / 15 edges at 5,2)
- tests/python/test_kneser_order_parity.py: 20 passed
- full tests/python suite: 21409 passed; 6 failures identical to HEAD
- Python-only change
