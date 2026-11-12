# Multigraph add_edge / from_dict_of_dicts O(E)->O(1) (br-r37-c1-mgaek)

## Structural defect (complexity-class, per no-ceiling addendum)
Two multigraph construction paths used ``self[u][v]`` (or ``graph[u][v]``) per
edge, which rebuilds the FULL MultiAdjacencyView (O(E), cache invalidated by the
per-edge edges_seq bump):
1. ``_multi_add_edge_auto_key`` (the PUBLIC MultiGraph/MultiDiGraph add_edge
   wrapper): computed the next parallel key via ``self[u][v]`` on every call ->
   the public multigraph ``add_edge`` is O(E); an 8000-edge add_edge loop took
   57s (vs nx 5ms).
2. ``_add_json_multiedge`` (from_dict_of_dicts / node_link_graph construction):
   ``graph[s][t][key].update(attrs)`` per edge -> from_dict_of_dicts of 8k edges
   took 137s (4864x slower than nx).

## Lever (O(1) keydict / live dict)
Replace ``self[u][v]`` with the native O(1) ``get_edge_data(u, v)`` (keydict; 1us
even on a 20k-edge graph) for the gap-aware key, and ``graph[s][t][k]`` with
``get_edge_data(s, t, k)`` (live dict) for the attr write. O(E^2) -> O(E).

## Isomorphism (bit-exact incl. gap-aware keys)
Same gap-aware key (nx.MultiGraph.new_edge_key: key=len(keydict); while key in
keydict: key+=1) -> explicit/auto key mixes still match nx. Golden 0-mismatch vs
nx: from_dict_of_dicts over Graph/DiGraph/MultiGraph/MultiDiGraph x 4 seeds x
3-level + 4-level (multigraph_input) inputs (FDOD_GOLDEN
cbc6225a95f369b263ec038b530a8be7ba4249b049703a7ed2a4e65da339fbe4), AND the
add_edges_from golden still passes (MGADD_GOLDEN d022a3fc...). 1149
from_dict/convert/node_link/multigraph/add_edge pytest pass.

## Benchmark (median)

    from_dict_of_dicts(MultiGraph, 8k edges)  124055 -> 60-67 ms  = ~1850-2071x self (4.2-4.9x vs nx)
    from_dict_of_dicts(MultiDiGraph, 8k)        ~1463 -> 57 ms     = ~25x self (3.1x vs nx)
    8000 add_edge loop (MultiGraph)            57025 -> 64 ms      = ~890x self

Eliminates two pathological O(E^2) construction paths. Residual ~3-5x vs nx is
the per-edge dual-rep tax (bulk/arena rewrite, br-r37-c1-71x9k). Pure-Python.
Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
