# degree_pearson_correlation_coefficient: vectorized degree pairs

Bead: `br-degpearsonfast`.

## Gap
`degree_pearson_correlation_coefficient` built every (deg_x, deg_y) pair via
`node_degree_xy`, which walks the slow DegreeView/EdgeView wrappers. Warm min-of-5
vs networkx: 6.2x SLOWER (n=600), 14.5x on the underlying degree_mixing path at
n=2000. (degree_assortativity_coefficient is already native-fast; this is its slow
node_degree_xy-based sibling.)

## Lever (one)
Pearson's r is invariant to the ORDER of the (x, y) pairs, so for the common case
(weight=None, nodes=None, simple non-multigraph, no self-loops) derive the degree
pairs from the native sparse adjacency (`to_scipy_sparse_array` COO + row/col sums)
in ONE vectorized pass, then `pearsonr(du, dv)`. self-loops / weighting / a nodes
subset / multigraphs fall back to the exact node_degree_xy path.

NOTE: the sibling degree_mixing_matrix was NOT changed -- its returned matrix's
row/col order depends on Python set-hash iteration order of the degree values,
which a vectorized mapping cannot reproduce on hash-collision cases (verified
fails 65/71 on adversarial wide-degree graphs). It stays on the exact path.

## Parity
150 random graphs (directed + undirected + self-loops) match networkx to 1e-7
(the tolerance the assortativity tests use); weighted / nodes-subset fallbacks and
the exact degenerate values (-1.0 for path/star) preserved. Test (5/5):
tests/python/test_degree_pearson_vectorized_parity.py.

## Benchmark (gnp p=0.02, warm min-of-5)
    n      nx        fnx       ratio
    600    4.81ms    2.62ms    0.55x (FASTER)
    2000   70.04ms   40.88ms   0.58x (FASTER)
From 6.2x SLOWER to ~1.8x FASTER than networkx.

## Files
- python/franken_networkx/__init__.py: _degree_xy_pairs_fast + fast path.
