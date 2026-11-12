# br-r37-c1-wvbzw (lever 2) — dfs canonical strings + discovery-object parity

## Residual gap (post lever 1)
dfs_tree 2.04x: dfs_edges converted kernel STRINGS -> PyObjects, then
dfs_tree re-canonicalized EVERY endpoint via node_key_to_string (a
per-edge Python round-trip), plus per-edge recorded add_node/add_edge.

## Lever: dfs_edges_canonical helper
Shared canonical-string edge stream; dfs_tree consumes strings directly,
builds nodes via extend_nodes_with_attrs_unrecorded / first-touch
extend_edges_unrecorded (one ledger record), display keys from the
source's maps.

## Found & fixed in the same surface: traversal DISCOVERY-object parity
nx yields the source AS PASSED and every discovered node as its parent's
adjacency-ROW object (z6uka overrides); fnx mapped through py_node_key —
mixed int/float keys diverged (28 vs 28.0), PRE-EXISTING at HEAD for the
whole traversal family. Added GraphRef::py_row_key + discovery
propagation in dfs_edges/dfs_tree. bfs_edges/bfs_tree + other traversal
iterators still have the old mapping — family bead filed.

## After
dfs_tree 1.13x directed / 0.85x undirected (was 8.82x pre-lever-1);
dfs_edges 1.25x (correctness-first disp map).

## Proof
battery: directed/undirected x depth limits + forest + mixed-key
tree/edges (sha 995fc874), 0 failures; 12-test committed file green;
full pytest 21598 passed, 0 failed.
