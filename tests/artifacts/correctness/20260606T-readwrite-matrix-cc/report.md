# Readwrite matrix (6 formats x 3 directions x attr VALUE TYPES)

graphml/gml/gexf/adjlist/edgelist/weighted_edgelist x
(nx->fnx, fnx->nx, fnx->fnx) with typed node/edge/graph attrs
(str/float/bool/int) — type names compared, not just values.

## Result: 16/18 clean; 1 bug (2 cells) found and fixed
fnx's native read_gexf dropped ALL graph-level attrs. nx GEXFReader
populates: mode (ALWAYS; 'dynamic' only when declared), node_default
(ONLY when a class=node <attributes> element exists), edge_default
(ALWAYS — the Gephi-0.7beta weight hack sets it last), plus
name/start/end when present — in that key order, defaults typed per
declared attribute type. New _restore_gexf_graph_metadata expat pass
mirrors it on the native path (sha e04810a2, key order pinned).
