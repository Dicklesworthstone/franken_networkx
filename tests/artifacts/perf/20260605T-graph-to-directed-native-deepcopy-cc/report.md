# perf: native deep-copying Graph->DiGraph kernel (to_directed) 4.19x->2.02x

Graph.to_directed() (copy case) ran _graph_to_directed_copy: a per-arc Python loop
(`for source in self: for target in self[source].items(): add_edge(...,**deepcopy(attrs))`)
— ~320k Python add_edge dispatches + per-arc adjacency materialization + deepcopy
of (mostly empty) attr dicts = ~4.2x slower than nx. The Multi/DiGraph siblings
already had native/batched paths; plain Graph was left on the per-arc loop.

Lever: added PyGraph::_native_to_directed_deepcopy — builds the DiGraph entirely
in Rust in nx's adjacency-grouped edge order (for source in nodes_ordered, for
target in neighbors(source) -> both directed arcs of each undirected edge),
deep-copying attrs via copy.deepcopy to honor nx's to_directed deep-copy contract.
Attr-less nodes/edges stay LAZY (no PyDict alloc / no py_dict_to_attr_map / no
deepcopy — a fresh dict materializes on demand), matching the native copy kernel.
Wired _graph_to_directed_copy to use it for exact Graph type (no nx private
storage, default to_directed_class); subclasses/as_view keep the generic rebuild.

Proof: to_directed_parity_proof.py — 1000 cases (attrs incl nested list, node/graph
attrs, self-loops) vs networkx: 0 mismatches on node order, edge order, edge/node/
graph attrs; deep-copy independence verified (mutating a result edge's nested list
does NOT touch the original). Edge cases: subclass falls back to DiGraph rebuild,
empty graph, self-loop — all correct.

Perf (release, n=8000 m=40000): to_directed 525ms -> 236ms = 2.22x self-speedup;
vs nx 4.19x -> 2.02x. Residual is the inner IndexMap edge construction (substrate
tax, kt0vp domain). to_directed underlies many directed-algorithm entry points.
