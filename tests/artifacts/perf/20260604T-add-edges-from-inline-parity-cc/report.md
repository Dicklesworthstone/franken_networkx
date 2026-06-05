# fix: add_edges_from inline parity (commit a250e836a, br-r37-c1-77ux3)

## Bug
nx.Graph/DiGraph.add_edges_from adds edges INLINE; a malformed edge mid-batch
leaves the valid PREFIX (and the failing edge's partial node) on the graph.
fnx validated the whole batch up front and added nothing on any error.

Repro: Graph().add_edges_from([(1,2),(3,4),(5,)])
  nx  -> nodes {1,2,3,4}, edges {(1,2),(3,4)}, then NetworkXError
  fnx -> empty graph (before fix), then NetworkXError

## Fix
Single inline-faithful scan: find first offending edge, add valid prefix via the
fast bulk Rust path, reproduce the failing edge's partial node (nx creates u
before examining v, so (1,None) keeps node 1), then raise the same nx error.
Replaces three Python pre-passes -> also marginally cheaper. All prior error
contracts preserved (bad-arity NetworkXError, len()-less TypeError, None
ValueError, unhashable TypeError, list->tuple normalisation, generator
partial-progress).

## Proof
50-case differential (Graph + DiGraph x 25 shapes), 0 mismatches vs nx,
byte-exact on resulting nodes + edges + edge-data + error class/message.
Shapes: partial-then-bad, u/v/both-None ordering, bad-arity tuples/lists/strings,
len()-less items (None/int), unhashable u/v (prefix-preserving), generators that
raise mid-stream, attrs applied to prefix, 3-tuple data, dup edges, self-loops,
empty, all-valid.
golden sha256: 9b814ecdaf6ff781aeb590abf7fb4cbe1b0c7f770135695b8f1e2b08c9cabe7e

Run: python3 differential_proof.py  (expects TOTAL cases=50 mismatch=0)
