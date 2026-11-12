# fix: MultiGraph adjacency-cell objects, z6uka phase 3a (br-r37-c1-z6uka)

## Contract (probed against nx)
- a cell is created by the FIRST key of a (u, v) pair; parallel keys
  (even reversed, other type) REUSE it without changing row objects
- edges(keys=True) v-side renders the CELL object for every parallel key
- removing one parallel key keeps the cell; removing the LAST key drops
  it (re-add creates fresh cell objects)
- copy()/subgraph().copy() re-derive via nx's u-major walk
- self-loops keep only v's object

## Implementation
PyMultiGraph.adj_py_keys (sparse) + py_adj_key/derive_copy_adj_py_keys;
populate in add_edge AFTER node_key_map insertion (a self-loop's first
endpoint object must already be stored to detect the v conflict);
exact-int explicit-key fast path now BAILS on display conflicts (it
bypassed populate: add_edge(36, 16, key=0) onto a node stored as 16.0);
maintenance in remove_node(s)/remove_edge (cell-empties check)/clear/
clear_edges; renders in MultiAtlasView (4 sites), adjacency walker,
keyed edges materializers. PyMultiDiGraph fields land as inert
scaffolding (phase 3b).

## Found during proof (filed separately)
- br-r37-c1-o1i86: MultiGraph __copy__ (copy.copy) scrambles adjacency
  ROW ORDER vs nx — uniform keys, pre-existing
- two MULTIDIGRAPH suite failures at pure HEAD are pre-existing (fixes
  live in a peer's uncommitted working-tree hunks)

## Proof
- pinned contract probes: base / rm-one-key / rm-last+readd / copy /
  subgraph all match nx; 20-trial random mixed-key corpus clean
- 6 new committed tests (20 total in test_adj_row_key_parity.py)
- full pytest on the COMMIT-CANDIDATE tree (HEAD + these changes,
  built from that exact tree): 21477 passed; all 6 failures reproduced
  at pure HEAD
- process: commit content staged from the compile-verified worktree
  via hash-object (the hunk-filter context-overlap mangling that the
  compile gate caught is bypassed entirely)
