# add_node 'n'-attr collision (br-r37-c1-7iria) — Phase B find

## How found
Phase B generative session (both perf beads peer-owned/exhausted under
load). Noise-immune sweeps: substrate surface (clean, prior session),
18-fn centrality/linalg numeric-type-leak (clean), then readwrite
typed-attr cross-impl interop — 8/18 cells errored.

## Root cause
Rust add_node binding: #[pyo3(signature = (n, **attr))]. An attr dict
with key 'n' (e.g. _from_nx_graph's `result.add_node(node, **attrs)`
after reading a graph whose nodes carry an 'n' attribute) bound the
node positionally to `n` AND passed n=<val> via kwargs ->
"got multiple values for argument 'n'". Broke read_graphml/read_gml/
read_pajek (and any **attr-splat caller) for such graphs.

## Fix
Rename the param to nx's public name `node_for_adding` across all four
classes. nx has the identical collision ONLY for an attr literally
keyed 'node_for_adding', so matching the name yields exact drop-in
parity (verified: 4-class collision battery agrees with nx).

## Proof
18-case readwrite cross-impl probe (graph6/sparse6/pajek/gml/graphml x
nx->fnx/fnx->nx/fnx->fnx) 0 divergences; 4-class direct collision +
'n'-attr battery; read_graphml('n'-attr) round-trip. Full pytest 21841.
Probe scripts archived here. (numeric-type sweep also archived: 18
centrality/linalg fns, 0 leaks.)
