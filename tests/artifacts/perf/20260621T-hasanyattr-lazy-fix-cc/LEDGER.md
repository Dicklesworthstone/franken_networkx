# CORRECTNESS FIX — graph_has_any_attrs lazy-mirror false-negative drops attrs in relabel/product/convert (br-r37-c1-hasanyattrlazyfix)

- Agent: `BlackThrush` · 2026-06-21 · Files: fnx-classes lib.rs+digraph.rs, fnx-python algorithms.rs
- Found by following the [[reference_lazy_edge_py_attrs_mirror_trap]] note (graph_has_any_attrs has the same shape).

## The bug (real, silent data loss)
`graph_has_any_attrs` scanned only the lazy `node_py_attrs` / `edge_py_attrs` Python MIRRORS.
On a freshly batch-built graph with EDGE attrs but NO node attrs (`Gf.add_nodes_from(nodes);
Gf.add_edges_from(edges, data=True)`), the edge mirror is unmaterialized -> returns False ->
relabel/product/convert take their no-attr fast path and DROP the edge attributes.
MEASURED: relabel_nodes(fresh edge-only weighted) returned edges with weight=None vs nx's
real weights. (The earlier graph_has_edge_attr fix dodged this only because that caller also
checked node attrs, which add_nodes_from(data=True) materializes.)

## The fix
fnx-classes Graph/DiGraph: `any_node_has_attrs()` / `any_edge_has_attrs()` (scan the inner
`nodes`/`edges` AttrMaps for a non-empty map — authoritative, populated by batch construction).
`graph_has_any_attrs` now returns `inner_node || inner_edge || mirror_node || mirror_edge`
(short-circuits before any PyO3 when the inner already proves presence).

## Verify
- graph_has_any_attrs == Python ref 1250/1250 (simple Graph/DiGraph: batch edge-only, node-
  only, python-set, plain). relabel(fresh edge-only) now preserves edge attrs. pytest -k
  'relabel/convert/product/graph_has/any_attr/quotient' 2469 passed 0 failed.

## Note
False-positive-safe: callers only SKIP attr-copying when this is False; over-reporting just
keeps the (correct) attr-preserving slow path. Second of the *_py_attrs-mirror lazy bugs
fixed this session (graph_has_edge_attr was first).
