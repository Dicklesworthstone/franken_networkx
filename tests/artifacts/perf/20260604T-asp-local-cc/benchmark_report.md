# all_simple_paths: reimplement DFS on fnx graph for small cutoff (br-r37-c1-asplocal)

all_simple_paths(source, target, cutoff) DELEGATED to networkx -- a full fnx->nx
graph conversion (O(V+E)) on every call -- so a small-cutoff query (the common
"paths up to length k" use) was 24-100x SLOWER than networkx (~1.9ms n=200 / ~6.8ms
n=600 at cutoff=2 vs nx ~0.05ms).

Lever (first-form conversion tax, br-r37-c1-a0nl0): for a non-multigraph with a
small integer cutoff (few paths), reimplement networkx's exact all_simple_edge_paths
DFS directly on the fnx graph -- same G.edges(node) iteration order, so the yielded
node lists AND their order are byte-identical. For a large cutoff / cutoff=None
(many paths) or a multigraph the one-time conversion amortises and networkx's C DFS
over the path explosion wins, so those keep delegating (no regression).

Proof: yield-order parity vs networkx 0 mismatches over 400 graphs (directed/
undirected/string, scalar+iterable target) x cutoffs {0,1,2,3}; golden sha256; 222
existing simple-path tests pass. (A pre-existing multigraph delegation order
divergence is unchanged and filed as br-r37-c1-qpykd.)

| n | cutoff | nx (ms) | fnx before | fnx after | speedup |
|---|---|---|---|---|---|
| 200 | 2 | 0.054 | 1.91 | 0.191 | 10x vs before |
| 600 | 2 | 0.063 | 6.83 | 0.242 | 28x vs before |
| 600 | 3 | 0.290 | 7.22 | 1.28 | 5.6x vs before |

before: small-cutoff ~24-100x SLOWER than nx (full conversion per call).
after:  ~3.5-4.3x slower than nx -- the conversion tax is gone; residual is the
        fnx G.edges(node) PyO3-per-edge tax (substrate). Large-cutoff/multigraph
        still delegate.
