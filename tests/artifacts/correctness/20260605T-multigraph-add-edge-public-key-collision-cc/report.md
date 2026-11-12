# fix: MultiGraph.add_edge auto-key matches nx (public key space, not internal usize)

br-r37-c1-mgkey. fnx stores MultiGraph edges under an INTERNAL usize key space and
maps to/from arbitrary PUBLIC Python keys (edge_py_keys / resolve_internal_edge_key).
For an auto add (key=None), PyMultiGraph::add_edge echoed the INTERNAL usize key as
the public key. nx instead computes `key = len(G[u][v]); while key in G[u][v]: key
+= 1` over the PUBLIC keydict. When an explicit public key (e.g. int 1) had been
added that mapped to a DIFFERENT internal key (e.g. 0) — reachable after
subgraph()/copy() rebuilds with mixed int/str keys + reversed (u,v) orientation on
undirected graphs — the internal-derived public auto-key COLLIDED with the existing
public key and silently OVERWROTE / duplicated that parallel edge (data loss).

Found by a multigraph key/parallel-edge fuzz (114/3000 sequences diverged; e.g.
add_edge(2,3,key=1) ... subgraph().copy() ... add_edge(3,2) returned public key 1
[collide] vs nx's 2). Minimal black-box repros matched; the trigger needs
accumulated state, so the fuzz is the proof.

Fix: in PyMultiGraph::add_edge, for key=None compute the PUBLIC int auto-key over
the current public key set (counting all keys for the len, skipping int collisions
exactly like nx) BEFORE adding, and store/echo THAT as the public key (not the
internal usize). MultiDiGraph is structurally safe (no canonicalization /reversed
orientation; internal==public for int keys) — verified 0 divergences over 2000
directed seeds, left untouched.

Proof: key_collision_fuzz.py + the in-session fuzz — 4000 sequences (undirected +
directed, add/remove/clear/copy/subgraph/keyed-mutation, mixed int+str keys):
before = 140 key divergences (undirected); after = 0 key divergences AND 0
final-state mismatches vs networkx.
