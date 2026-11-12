# nodes_with_selfloops multigraph route (br-r37-c1-mgselfloopnodes, cc)

nodes_with_selfloops_rust raises on multigraphs, so MG/MDG fell to the Python generator (node for node in G.adj if node in G.adj[node]) which materializes a per-node AdjacencyView -> ~1175x slower than nx. Routed multigraphs to the existing native _native_selfloop_nodes scan (node-order-exact, same binding selfloop_edges uses); simple graphs keep nodes_with_selfloops_rust.

MG nodes_with_selfloops 0.00x -> 2.04x (fnx 0.0040ms / nx 0.0083ms; ~1000x self-speedup from 3.99ms). Byte-identical node order; 0 fails across MG/MDG/simple/empty + multi-selfloop. Full suite 49239 passed, same 5 pre-existing.
