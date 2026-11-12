# perf+fix: set operators replicate installed nx verbatim (br-r37-c1-aun4c)

## Problems (one family, one lever)
- intersection_all: fnx walked graphs[0] insertion order; installed nx
  builds set(G.nodes)/set(G.edges) (+BOTH orientations for undirected),
  intersects in-place, and add_*_from the SETS — node AND edge order
  silently DIVERGED (latent parity bug).
- intersection (2-arg): full nx round-trip (~6.99x) to dodge exactly
  that order problem.
- difference 8.39x / symmetric_difference 8.02x: simple path =
  _raw_difference + rebuild (rebuild-tax-bound); multigraph path =
  full nx round-trip. Also br-diffnodes' early node-set check fired
  BEFORE nx's multigraph-mismatch error on doubly-invalid inputs.

## Lever
Replicate installed nx VERBATIM in pure Python (jv0h5 kneser
principle — identical set construction sequences give identical
CPython set iteration): intersection_all rewritten; intersection =
intersection_all([G, H]) (nx's own definition); difference /
symmetric_difference with nx's exact check sequence +
create_empty_copy(with_data=False) copy depth, per-edge loops batched
into one add_edges_from per pass (incl. MultiGraph keyed edges —
round-trip dropped). _raw_symmetric_difference triaged keep-public-api.

## Proof
0 failures: 48 op-cases (4 classes x 4 trials x 3 ops, weighted
sources), 3-graph intersection_all (Graph/MultiGraph/DiGraph), error
contracts in nx's exact SEQUENCE (multigraph mismatch before node-set
check; empty-list ValueError), no-attrs copy-depth checks.
GOLDEN_CORPUS_SHA256: 2e2f6ca40250fa7977055dd96a19261d133a8d03f32601b484da199f2265c9ee

## Bench (interleaved warm min-of-8, n=1500/E~5217 pairs)
- intersection:          6.99x -> 2.02x
- difference:            8.39x -> 3.06x
- symmetric_difference:  8.02x -> 3.25x
- residual = construction substrate (w1dm8)

## Validation
- tests/python/test_setops_order_parity.py: 17 passed
- full tests/python suite: 21457 passed; 6 failures identical to HEAD
- Python-only change (+ TRIAGE entry in scripts/)
