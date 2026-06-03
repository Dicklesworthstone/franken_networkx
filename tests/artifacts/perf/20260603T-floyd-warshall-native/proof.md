# Native in-place SIMD Floyd-Warshall, 2.28x self / 1.3-1.5x faster than nx (br-r37-c1-fwdense)

## Alien primitive (per no-ceiling addendum)
Replaced numpy's broadcast all-pairs Floyd-Warshall — `for k: A = minimum(A,
A[:,k:k+1] + A[k:k+1,:])`, which allocates n temporary n*n arrays and is
memory-bandwidth bound — with a **cache-friendly in-place SIMD min-plus FW**: a
different memory/vectorization model (zero temp allocations; per-pivot read-only
row snapshot removes the read/write alias so the inner v-loop is a fused min-add
over a contiguous slice that auto-vectorizes). The dense matrix is also built
natively (no AtlasView walk). This is an algorithmically-different swing, not a
view micro-lever.

## Bit-exactness (proof)
For pivot k, `dist[k][*]` and `dist[*][k]` are invariant during the k-iteration
(`dist[k][k]==0` => self-updates are no-ops), so a read-only snapshot `row_k =
dist[k]` gives, for every (u,v): `min(dist[u][v], dist[u][k] + row_k[v])` ==
numpy's `min(A, A[u][k] + A[k][v])` — identical operands, identical min/+,
order-invariant across (u,v). Skipping rows with `dist[u][k]==inf` is exact.
Build matches nx `to_numpy_array(nonedge=inf)` + `fill_diagonal(0)`: weight or
default 1.0, min over parallel, self-loops dropped (diagonal 0).

Golden 0-mismatch vs nx over Graph + DiGraph x 3 seeds x sizes {(40,150),(60,80),
(30,400)} x weight modes {rand, none(default 1), zero} x self-loops on/off +
negative weights:

    mismatches=0
    FW_GOLDEN 2105f67572c396f9e4c5029443f85a11091c746e1bff11c72e13d37f2b7f8433

1932 floyd/warshall/shortest/distance pytest cases and `clippy -D warnings` pass.
Gated on simple Graph/DiGraph + default nodelist + str weight (subclasses /
SubgraphViews / multigraph / nodelist fall back to numpy).

## Benchmark (floyd_warshall_numpy, median)

    n=400 e=4000:  fnx 91.27 -> 40.07 ms (2.28x self);  nx 51.50 ms => 1.29x faster than nx
    n=300 e=2000:  fnx 40.36 -> 17.94 ms (2.25x self);  nx 26.23 ms => 1.46x faster than nx
    n=200 e=1000:  fnx 15.78 ->  6.32 ms (2.50x self);  nx  7.32 ms => 1.16x faster than nx

Flips fnx from ~1.75x SLOWER than nx to ~1.3-1.5x FASTER. Score = Impact 5 x
Confidence 5 / Effort 3 = 8.3.

## Next primitive (keep digging)
The native build (~28ms of the 40ms at n=400, PyO3 per-edge dict reads) is the
next target: a zero-copy COO->dense fill / reuse adjacency_arrays to drop it to
~5ms => ~17ms total => ~3x faster than nx. Then blocked std::simd GEMM for the
spectrum/katz dense ops.
