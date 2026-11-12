# fix: tensor_product / strong_product edge-order parity with networkx

## Bugs
Both products produced the correct EDGE SET but a divergent EDGE ORDER vs nx
(cartesian_product and lexicographic_product were already correct).

1. tensor_product: nx emits the cross edges in TWO passes —
   `_directed_edges_cross_edges` (all (gu,hu)-(gv,hv)) then, undirected only,
   `_undirected_edges_cross_edges` (all (gv,hu)-(gu,hv)). fnx interleaved both
   per edge-pair.
2. strong_product: nx orders the two Cartesian passes OPPOSITE to
   nx.cartesian_product — strong does `_nodes_cross_edges` (nodes x H-edges)
   THEN `_edges_cross_nodes` (G-edges x nodes), whereas cartesian_product does
   the reverse. fnx built strong on top of cartesian_product() (wrong cartesian
   order) and then interleaved the tensor cross edges.

## Fix
- tensor_product: split the cross-edge loop into nx's two passes.
- strong_product: stop reusing cartesian_product; build the 4 edge passes
  directly in nx's exact order (nodes x H-edges, G-edges x nodes, tensor
  directed cross, tensor undirected cross) with matching edge attrs
  (H-edge attrs / G-edge attrs / paired attrs respectively).

## Proof
parity_proof.py: 144 cases — tensor/strong/cartesian/lexicographic over
{Graph,DiGraph,MultiGraph,MultiDiGraph} x base/factor specs, with node attrs +
edge attrs + parallel edges — full node order, edge order (with keys for
multigraphs), and edge/node attrs vs networkx: 0 mismatches. golden_sha256
ab9ca8e7ce3f5ba397442be33404755c5c0a24b8ca8c8e6ac6124f4b5a04f765.
parity_proof_random.py: 64 larger gnp cases (all 4 types, self-loops, weights,
multigraph): 0 mismatches.

Pure-Python parity fix (these operators don't use a Rust kernel). NOTE: full
pytest currently blocked by an unrelated maturin/.so rebuild issue in
TealSpring's in-flight Rust; validated via the direct nx differential above.
