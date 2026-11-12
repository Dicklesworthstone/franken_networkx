# numeric/attribute assortativity: vectorize via native edge-index arrays

Bead: `br-assortfast`.

## Catastrophe
numeric_assortativity_coefficient and attribute_assortativity_coefficient went
through attribute_mixing_matrix -> the slow node_attribute_xy iterator (per-edge
walk over DegreeView/EdgeView/NodeView wrappers). Warm min-of-N vs networkx: ~2.35x
/ 2.26x SLOWER at n=800.

## Lever (one)
The numeric coefficient is the Pearson correlation of the attribute values across
edges (order-invariant); the categorical coefficient ((trace - sum(M@M))/(1-...))
is invariant to the category->index mapping. For the common case (undirected
simple graph, no self-loops, nodes=None) get the edge endpoint INDEX arrays
natively (adjacency_default_order_index_arrays -- both directions of each
undirected edge, 0.28ms vs 3.9ms for a full scipy COO build) and compute Pearson's
r MANUALLY (avoiding scipy.stats.pearsonr's p-value overhead) / the trace formula
in one vectorized pass. Directed / multigraph / self-loop / nodes-subset / nx-typed
inputs fall back to the exact attribute_mixing_matrix path.

## Proof
test_assortativity_vectorized_parity.py (5/5): 150 graphs (directed + undirected +
multigraph + self-loop fallback) match networkx to 1e-7; nx-typed input + nodes
subset + missing-attr KeyError + perfect-alternating clean value all preserved.

## Benchmark (gnp, warm min-of-N)
    function   before    after
    numeric    2.35x     0.45x (2.2x FASTER)
    attribute  2.26x     0.52x (1.9x FASTER)
From ~2.3x SLOWER to ~2x FASTER than networkx.

## Files
- python/franken_networkx/__init__.py: numeric_assortativity_coefficient +
  attribute_assortativity_coefficient fast paths.
