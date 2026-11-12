# JSON-graph family matrix: 39/39 CLEAN
node_link/adjacency/cytoscape (x4 classes) + tree, each x
(nx->fnx, fnx->nx, fnx->fnx) with JSON-normalized payloads and typed
attrs (str/float/bool) incl. multigraph keys. Zero divergences —
certification only, no fixes needed. (Third consecutive clean matrix:
parity surface coverage is converging.)

# union/compose residual: profiled and classified
cProfile (split-reliable under load): 100% inside _native_compose;
binding-level walk already optimal post lever-6. Residual = per-edge
EdgeKey(String,String) allocs = the String-keyed substrate class
(joins the 68-76% String-adjacency-tax evidence). l5ve7 CLOSED with
scoreboard; substrate epoch filed separately.
