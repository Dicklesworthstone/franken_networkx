# VERIFICATION — broad conformance GREEN after the session's correctness fixes + clustering/assortativity sweep

- Agent: `BlackThrush` · 2026-06-21 · MEASURED

## Conformance (post all session changes incl Rust attr-check fixes)
pytest -k 'relabel/convert/product/attr/clique/clustering/dijkstra/voronoi/spanning/
second_order/size/boundary/simple_path/centrality/to_directed/to_undirected/copy/reverse/
union/compose/degree' -> 14817 passed, 463 skipped, 1 xfailed, 0 FAILED. The two lazy-mirror
fixes (graph_has_edge_attr c9aded59c, graph_has_any_attrs 950d9632a) + the katz/subgraph/
communicability/all_simple_paths/edge_boundary/size perf wins are all green together.

## Sweep this turn (clustering / assortativity / cliques) — DOMINATED
transitivity 85.4x, average_clustering 54.2x, rich_club_coefficient 56.9x, eccentricity 11.3x,
degree_assortativity(weighted) 4.4x, generalized_degree 3.8x, average_degree_connectivity 2.8x,
clustering(weighted) 2.26x, node_clique_number 1.48x.
Residuals (tiny, no clean lever): triangles(nbunch) 0.80x (already locally-optimized; constant
~17us setup, doesn't scale), number_of_cliques 0.83x (find_cliques AND the Counter are both
parity — the gap is generator-drive noise, not a fixable hotspot).

## Open (documented separately, 435776579)
to_directed()/to_undirected() drop edge attrs on a FIRST-OP int-node batch-built graph — a
construction-kernel index-space inconsistency (adj_indices vs self.edges), NOT covered by
current conformance (those tests use materialized/other graphs). Needs an extend_edges_*_
unrecorded storage-consistency pass; 3 conversion-layer fixes failed (reverted).
