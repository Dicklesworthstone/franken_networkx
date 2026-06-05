# fix: add_weighted_edges_from inline parity (br-r37-c1-77ux3 sibling)

## Bug
nx.add_weighted_edges_from delegates to add_edges_from((u,v,{weight:w}) for ...),
which creates node u BEFORE examining v. So an edge whose v is None/unhashable
still leaves u on the graph before raising. fnx validated both endpoints up front
(if u is None or v is None: raise; hash(u); hash(v)) and dropped that partial node.

Repro: Graph().add_weighted_edges_from([(1,2,5),(7,None,9)])
  nx  -> nodes {1,2,7}, edge (1,2), then ValueError("None cannot be a node")
  fnx -> nodes {1,2}    (before fix)

## Fix
Match nx ordering: validate+create u (None->raise, hash->TypeError), THEN examine v;
if v is None/unhashable, add_node(u) before raising.

## Proof
52-case differential (Graph/DiGraph/MultiGraph/MultiDiGraph x 13 shapes:
bad arity short/long, u/v None, u/v unhashable, custom weight key, attrs,
self-loops, dups, empty, all-valid), 0 mismatches vs nx, byte-exact on
nodes + edge-data + error class/message.
golden sha256: 6ddf6e48b6d4d48d0f22d73d525983d44dc237ed17835cf85ec012d7a7f73769
