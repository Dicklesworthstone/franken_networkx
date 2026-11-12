# generate_multiline_adjlist: build from native to_dict_of_dicts (kill per-edge PyO3)

## Gap
generate_multiline_adjlist simple-graph path called G.get_edge_data(node, nbr)
once PER EDGE — a PyO3 round-trip per edge (~2400 on a 400-node watts_strogatz).
fnx 1.652ms vs nx 0.561ms = 2.9x SLOWER.

## Lever (one, pure-Python — native kernel already exists)
The native to_dict_of_dicts kernel returns {node: {nbr: attrs}} in ONE call
(node + adjacency order preserved, byte-identical attr dicts; it already beats
nx 1.75x for to_dict_of_dicts). Build the multiline lines from that snapshot
instead of per-edge get_edge_data. Simple Graph/DiGraph only; views/subclasses
keep the per-edge fallback.

## Behavior parity / golden sha256 (MY EDITS == HEAD)
6d60f440d581f567edab20541e6811c2210d43e373b6e802c0ea97e2e6914c5b
(35 graphs: weighted watts_strogatz Graph+DiGraph, isolated nodes, self-loops,
complete, path, empty.) vs upstream nx: 0 mismatches. 119 readwrite/adjlist
tests pass.

## Speed (watts_strogatz n=400, weighted, min of 25)
1.652ms -> 0.614ms = 2.69x self-speedup; 2.9x-slower-than-nx -> ~parity
(nx 0.588ms). Removes ~2400 per-edge get_edge_data PyO3 round-trips.
