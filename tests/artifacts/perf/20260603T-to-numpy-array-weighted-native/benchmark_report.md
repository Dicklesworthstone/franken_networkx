# to_numpy_array weighted native COO path

Lever: extend `to_numpy_array`'s native Rust COO builder (previously gated on
`weight is None`) to the weighted case (string `weight` key). Sync
Python-visible edge attrs into Rust storage, then scatter the f64 weights into
the pre-allocated dense matrix. Unlike `to_scipy_sparse_array`, no native
int/float dtype inference is needed: the matrix dtype is already fixed by
`np.full(..., nonedge, dtype=...)` (float64 for the default nonedge=0.0), so
the f64 native data scatters in exactly as the Python `G._adj` loop would
assign `edge_attrs.get(weight, 1)`.

Previously the weighted default (`weight="weight"`) fell to a pure-Python
`G._adj.items()` loop — ~11x slower than nx.

## Benchmark (python time.perf_counter, 20 reps, attrs on 1/3 edges)

| graph                     | nx       | fnx before | fnx after | gap after |
|---------------------------|----------|------------|-----------|-----------|
| n=1500 m=12000 undirected | 13.34 ms | 86.11 ms   | 26.81 ms  | 2.01x     |
| n=1500 m=12000 directed   | 7.04 ms  | 33.84 ms   | 20.78 ms  | 2.95x     |
| n=2000 m=20000 undirected | 18.05 ms | 171.85 ms  | 42.18 ms  | 2.34x     |
| n=3000 m=30000 undirected | 62.04 ms | ~          | 103.24 ms | 1.66x     |

Self-speedup ~3.2x; gap vs nx 11.27x-slower -> ~2.0x-slower (n=1500).

## Isomorphism + golden proof

162/162 configs byte-exact vs networkx: {undirected,directed} x
{none,all,mixed weights} x dtype {None,float,int} x nonedge {0.0,-1.0,2.0} x
weight {"weight","absent_key",None}, plus self-loops, mixed int/float weights,
nodelist subset/reorder, and a post-creation `G[u][v][k]=v` mutation
(staleness guard -- confirms the Rust attr sync). 587 existing matrix tests pass.

GOLDEN sha256 of matrix bytes (n=300 m=3000 undirected, mixed weights):
0773c8e516dbef7f4a214a7448b2a71e20788d525a80e76eee93c61575cc353d
(nx == fnx)

## Residual / follow-up

Residual ~2x is the COO scatter + sync overhead vs nx's vectorized fill; the
multigraph and explicit-dtype-with-int-inference cases still use the Python
path. to_pandas_adjacency (10.5x) shares the dense-fill shape and can reuse
this once it routes through to_numpy_array.
