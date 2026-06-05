# fix: dominance_frontiers start-node / back-edge parity with networkx

## Bug
`dominance_frontiers(G, start)` diverged from networkx whenever a predecessor of
`start` exists (back edge to the root). The native `_raw_dominance_frontiers`
kernel only walked >=2-predecessor join points and terminated at idom[u]; it
omitted nx's start-node special case. networkx does
`idom = immediate_dominators(G, start) | {start: None}` and processes `u == start`
(not just >=2-pred nodes), so each predecessor of start walks all the way up to
the root (idom[start]=None) — adding `start` to the frontier of every node on
those paths.

Example: G = 0->1, 0->2, 1->3, 2->3, 3->0, start=0:
  nx : {2:{3}, 1:{3}, 3:{0}, 0:{0}}
  fnx: {1:{3}, 0:set(), 2:{3}, 3:set()}   (missed 3:{0} and 0:{0}; wrong key order)

## Fix
Reimplement nx's exact algorithm in the Python wrapper on top of
`immediate_dominators` (verified key-order- and value-identical to nx over 350
random digraphs). idom key order drives the result dict key order, matching nx.
Bypasses the buggy native kernel. Pure-Python; undirected still raises
NetworkXNotImplemented (via immediate_dominators), multidigraph works.

## Proof
parity_proof.py: 402 cases — 5 explicit (back-edge/cycle/DAG) + 397 random
digraphs — comparing frontier VALUES, result dict KEY ORDER, and error parity
(start-not-in-G) vs networkx: 0 mismatches. Undirected + MultiDiGraph edge cases
verified. 25 dominance pytest pass. golden_sha256
b92e3c60e7e762257dba23a6812138f5feae2db640bfefbd8b052e45f8953b2a.
