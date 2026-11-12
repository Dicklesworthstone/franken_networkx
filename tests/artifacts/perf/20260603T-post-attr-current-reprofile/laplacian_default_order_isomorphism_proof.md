# Isomorphism Proof

## Scope

The new path is entered only for exact `Graph`, default `nodelist=None`, simple non-multigraph input, and when `_native_adjacency_default_order_index_arrays` is available. Explicit nodelists, `DiGraph`, multigraphs, subclasses, and weighted/present-attribute fallbacks keep the old route.

## Ordering

Default nodelist order is still `list(G)`. The default-order helper emits COO coordinates by native insertion-order node index and neighbor-index order, which is the same multiset used by the existing default-order sparse export path. The returned matrix is still canonicalized through `scipy.sparse.coo_array(...).tocsr()`.

## Tie-Breaking

Sparse matrix construction has no algorithmic tie-break. COO duplicate handling and CSR canonicalization remain delegated to SciPy exactly as before.

## Self-Loops And Degree

Rows and columns contain the same adjacency coordinates as the prior generic helper. Degree still uses `np.bincount(rows)`, self-loop rows still subtract from the diagonal contribution, and self-loop-only zero diagonals remain omitted.

## Dtype And Floating Point

The default unweighted path still creates `int64` diagonal and edge data. No floating-point arithmetic is introduced.

## RNG

The implementation uses no RNG. The benchmark graph seed is fixed at `12345`.

## Golden SHA

Baseline FNX, after FNX, and NetworkX oracle all produced:

`bca361dbcc78a18bc70f73d2dec30cc09d245e30218842df631d2bd79c1a2306`
