# edge_subgraph view .copy()/materialize fast-path (br-r37-c1-edgesubcopy, cc)

edge_subgraph returns a filtered live view; .copy() (and the coerce-materialize path) iterated the filtered VIEW's edges() — per-edge view-wrapper overhead, 41ms .copy() on a 2k-edge multigraph. The selected edges are already on filter_edge; apply that same set-lookup filter_edge directly to the NATIVE parent edges (same filter, same parent-iteration order). Fixed both _FilteredGraphView.copy() and _materialize_filtered_view.

MG edge_subgraph().copy() 0.13x -> 2.28x (17x self); MDG ->1.06x, G ->1.64x, DG ->1.20x. Byte-identical: node+edge order + attrs, 0 fails across all 4 graph types vs current .copy() and vs nx. Full suite 49239 passed, same 5 pre-existing.
