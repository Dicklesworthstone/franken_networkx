# Graph node iteration reuses the cached node-key tuple (br-r37-c1-fpssi follow-up)

## Lever
The 4 graph __iter__ (set(G) / for n in G) rebuilt N Python node objects per call
via py_node_key. Route them through cached_node_key_vec (clone_ref of the
nodes_seq-keyed cached tuple from fpssi) instead. The existing per-next nodes_seq
mutation guard is unchanged.

## Proof
- list(G)/set(G) parity 0 mismatches (4 classes x 20 seeds), node ORDER preserved.
- mutation-during-iteration still raises RuntimeError("dictionary changed size...")
  on all 4 classes; warm re-iteration correct.
- Full test suite green (7495 passed in the iterator-related slice; full run exit 0).
- set(G) n=1500: 710us -> 520us (~1.37x); node-key reconstruction removed from
  iteration.

## Honest residual (NEXT LEVER, filed separately)
set(G) is still ~35x nx (520us vs 14.5us). The dominant cost is now the GUARDED
PyO3 iterator protocol: NodeIterator.__next__ is a Python-level call per element
that borrows the graph to read nodes_seq for immediate mutation detection. nx
iterates its node dict at C level. Closing this needs either a C-level iterator
(loses the mutation guard) or a borrow-free guard (e.g. nodes_seq behind a shared
Arc<AtomicU64> the iterator reads without borrowing the graph). That is the real
remaining lever; this commit removes only the node-key-construction component.
