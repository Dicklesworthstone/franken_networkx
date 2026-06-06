# br-r37-c1-c1gz0 — node/edge_connectivity disconnected short-circuit

## Gap (warm min-of-3, /data/tmp/fnx_nodeconn2.py)
- disconnected (n=1500, E=1200, self-loops): fnx 6.02ms vs nx 0.01ms = 562x
  slower — 90% _fnx_to_nx conversion inside _call_networkx_for_parity,
  paid by the self-loop/multigraph/flow_func delegation branches just to
  learn the answer is 0.
- connected undirected: 1.01x (flow work dominates, no gap).
- directed: 0.06x (fnx native already 17x faster).

## Lever (one)
Mirror nx's GLOBAL-branch short-circuit natively in BOTH wrappers before
the delegation branches: directed -> not is_weakly_connected => 0;
undirected -> not is_connected => 0 (fnx natives: 8µs / 0.4ms). nx never
consults flow_func/cutoff on disconnected inputs either; s/t local calls
bypass the guard (s is None gate).

## After
- disconnected: 0.00ms vs nx 0.01ms = 0.21x (5x FASTER than nx).
- connected: 1.00x (unchanged). directed: 0.06x (unchanged).
- Score: impact 562x->0.21x on the affected shape, trivial effort => >>2.0.

## Proof
- 120-case matrix (2 fns x directed x multi x self-loops x 7 sizes +
  s/t-on-disconnected + flow_func + cutoff): 2 failures = PRE-EXISTING
  single-node-DiGraph edge_connectivity quirk (nx raises 'source and sink
  are the same node'; reproduced at HEAD build, filed br-r37-c1-0d8y3).
- 26 new committed tests (test_connectivity_wrappers.py) + 144-test
  connectivity battery green.
- full pytest 21542 passed, 0 failed.
