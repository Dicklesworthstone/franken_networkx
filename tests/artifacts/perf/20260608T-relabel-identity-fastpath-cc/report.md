# relabel_nodes / convert_node_labels_to_integers: identity-mapping fast path (br-r37-c1-relabelid)

## Problem
relabel_nodes(copy=True) rebuilds the graph edge-by-edge (G.edges(data=True)
iteration + add_edges_from, ~4ms/4k edges = the construction tax). convert_node_
labels_to_integers on a graph already labelled with the target integers maps i->i
(IDENTITY) yet paid the full rebuild -> 3.06x SLOWER than nx.

## Lever
A strictly-identity mapping (every entry k==v) makes relabel a pure copy
(copy=True -> native inner.clone, ~14x faster than the rebuild) / no-op
(copy=False -> return G). Gate on `all(k==v for k,v in _map.items())` per ENTRY
(NOT "no effect on this graph's nodes": a cyclic mapping {x:y,y:x} whose keys
aren't graph nodes must still raise like nx). Short-circuits on the first renamed
entry, so real relabels pay ~O(1).

## Proof
- Parity 0/180 (convert + relabel identity + relabel non-identity x int/string
  keys x attrs); copy=False identity returns the same object; cyclic-overlap
  copy=False still raises nx's exact error; pytest -k relabel/convert 70 passed.
- Speed: identity relabel 6.16ms->0.44ms (14x, == copy); convert_node_labels_to_
  integers n=1000 (range/identity) 3.06x slower -> ~0.3-0.55x = FASTER than nx.

## Follow-up (filed)
General (non-identity) injective relabel is still the construction tax (add_edges_
from). The big lever is a NATIVE relabel: clone inner (structure by integer index
is preserved) + rename the nodes IndexMap keys in order -> O(V), skipping the
O(V+E) edge rebuild entirely.
