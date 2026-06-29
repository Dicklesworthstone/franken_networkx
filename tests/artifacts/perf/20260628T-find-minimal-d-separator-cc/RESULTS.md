# find_minimal_d_separator de-delegation — CopperCliff 2026-06-28

## Problem
find_minimal_d_separator delegated to nx via the full O(V+E) _networkx_graph_for_parity
conversion for a single small query over only the ancestral subgraph of {x,y,included}
-> 0.15-0.17x vs nx (consistent across seeds).

## Fix (pure Python, br-cc-dsepinproc)
Run nx's EXACT algorithm (van der Zander & Liskiewicz 2020) in-process: ancestral set
via native ancestors(), one bulk adjacency snapshot restricted to that set, Bayes-Ball
_reachable over plain dicts. The _reachable uses a SET for the 'processed' membership
(nx uses a list -> O(E*|processed|)); same reachable set, O(E). Gated to plain DiGraph;
SubgraphViews/multigraphs/nx-private storage keep delegation.

## Measured
n=200: 0.15x -> 4.5x ; n=500: 0.88x -> 23.8x ; n=1000: -> 74.2x
(win GROWS with n: beats both the conversion tax AND nx's O(E^2) reachable.)

## Correctness
- 0/163 byte-exact through the wrapper (x/y/included/restricted, node+set inputs)
- error contracts match: non-DAG->NetworkXError, bad-node->NodeNotFound, disjointness
- result is a deterministic SET (content-compared)
- 179 d-separation + 757 dag/moral/ancestors conformance tests pass
