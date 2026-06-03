# Isomorphism Proof: tree center leaf trimming

## Change
`center(G)` now uses a private `_tree_center_unweighted` leaf-trimming helper only for unweighted, undirected, non-empty trees with no precomputed eccentricity dictionary and `usebounds=False`.

## Ordering Preserved
Yes. The helper uses `dict(G.degree)`, preserving node insertion order for remaining center candidates, and returns `list(center_candidates_degree)` exactly like `nx.tree.center`.

## Tie-Breaking Unchanged
Yes. Tree center can have one or two nodes. For two-center trees, output order follows original node insertion order, matching NetworkX's dictionary order. Non-tree and weighted paths still use the previous delegate/eccentricity behavior.

## Floating-Point
N/A for the new path. It only handles unweighted trees and returns node labels.

## RNG
N/A. The benchmark fixture is deterministic `path_graph(1500)`.

## Golden Outputs
- Center baseline FNX SHA: `8040836446332e628601060837cf031f58d89918048d3b65cf12fad0a7f49831`
- Center NetworkX SHA: `8040836446332e628601060837cf031f58d89918048d3b65cf12fad0a7f49831`
- Center after FNX SHA: `8040836446332e628601060837cf031f58d89918048d3b65cf12fad0a7f49831`
- All-output baseline FNX/NX SHA: `ded31e37db96e807e690e4092edffee407a0ef980cf0ca7274dd4806ac8caf12`
- All-output after FNX SHA: `ded31e37db96e807e690e4092edffee407a0ef980cf0ca7274dd4806ac8caf12`

## Guard Surface
- `e is not None`: unchanged delegate.
- `usebounds=True`: unchanged delegate.
- `weight is not None`: unchanged delegate.
- Empty graph: unchanged delegate/exception behavior.
- Directed graph: unchanged native directed eccentricity path.
- Non-tree graph: unchanged eccentricity path after `is_tree(G)` false.
