# perf: O(degree) MultiGraph/MultiDiGraph remove_node via swap_remove (nx-parity)

Bead: br-r37-c1-p6bxu (extends 6c721e942, the DiGraph swap_remove win).

## Lever
After 3a9b16201, `MultiGraph::remove_node` (fnx-classes/src/lib.rs) and
`MultiDiGraph::remove_node` (fnx-classes/src/digraph.rs) dropped incident edge
buckets with an O(|distinct pairs|) `retain` scan over the whole `edges`
IndexMap. But that map's ORDER is never observed externally: every public
consumer reads via `edges_ordered` (which walks node->neighbor / node->successor
order), and neither Multi struct has any internal map-order consumer
(MultiGraph/MultiDiGraph have NO `to_undirected` and NO CSR `edge_index`
cache — verified). So each incident bucket — known exactly from this node's
adjacency / successors+predecessors — can be dropped with O(1) `swap_remove`
instead of the O(|E|) retain scan. remove_node is now O(degree), matching nx.

- MultiGraph: one `swap_remove(EdgeKeyRef::new(node, neighbor))` per distinct
  neighbor (self-loops included as the (node,node) bucket); sum `bucket.len()`.
- MultiDiGraph: out-edges from `successors`, in-edges from `predecessors`. A
  self-loop's (node,node) bucket appears in both walks but `swap_remove` returns
  `Some` only the first time, so it is counted exactly once.

## Correctness (isomorphism / byte-exact parity)
- Rust A/B tests (`ab_bench_multigraph_remove_node`,
  `ab_bench_multidigraph_remove_node`) build identical n=1000 m=8000 multigraphs
  and remove the same 500 nodes via both the new swap_remove path and a
  reimplemented old retain path, then assert equal `node_count`, `edge_count`,
  AND full `edges_ordered()` (u,v,key,attrs). swap_remove reorders the private
  `edges` map but `edges_ordered` reads via adjacency order, so results are
  byte-identical.
- Python differential vs networkx (`parity_proof.py`): 60 random cases (30
  MultiGraph + 30 MultiDiGraph) with parallel edges, self-loops, and edge attrs;
  remove a random node sequence from both fnx and nx. 0 mismatches on node order,
  edge order (u,v,key), and edge attrs.
  golden_sha256 over the post-removal edge listings:
  `d0d9186abc34a4bf53a17f515e401bcd86edd54f15b70a4d5fc8693cb191c564`
- 62 fnx-classes cargo tests pass; clippy clean.

## Perf
Rust substrate A/B (release, identical n=1000 m=8000, 500 removals, byte-exact):
- MultiGraph   remove_node x500: retain 62.97ms -> swap_remove 13.14ms = 4.79x
- MultiDiGraph remove_node x500: retain 65.35ms -> swap_remove 11.98ms = 5.45x

Python end-to-end (current build, x500 on n=1000 m=8000): MultiGraph 15.6ms
(7.1x vs nx), MultiDiGraph 13.5ms (10.0x vs nx). The substrate is now O(degree);
the residual vs nx is the PyO3 per-call String-canonicalisation tax that bounds
all node-keyed ops (same residual character as the DiGraph case in 6c721e942).

## Note on the shared index
On commit the shared git index held a stale/conflicting snapshot of digraph.rs
(reverting both 6c721e942's DiGraph swap_remove and cbffefac7's to_undirected
parity fix). My working tree was correct (HEAD + only the Multi swap_remove
additions); committed via a private GIT_INDEX_FILE seeded from HEAD to land only
my two source files + this artifact bundle without clobbering peers' in-flight
files or propagating the bad index.
