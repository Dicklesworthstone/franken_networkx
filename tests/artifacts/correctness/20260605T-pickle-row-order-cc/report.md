# br-r37-c1-u3qyn — pickle round-trip preserves adjacency structure verbatim

## Bug
nx pickles the dict structure as-is. fnx __setstate__ REBUILT:
- Graph/MultiGraph/MultiDiGraph from edges_ordered = the u-major
  adjacency WALK -> rows re-derived in walk order (scrambled vs source;
  copies' walk-reordered rows also lost);
- DiGraph from the edge_py_attrs HashMap = RANDOM iteration order
  (round-trip edge AND row order was luck; sparse-mirror attr-less
  edges were silently DROPPED);
- all four classes dropped the z6uka display-object override maps
  (mixed int/float keys reverted to node-map objects).

## Fix (one lever: serialize structure explicitly, optional fields)
__getstate__ adds "adj_rows" (undirected) / "succ_rows"+"pred_rows"
(directed) with canonical keys in row order, plus the sparse
"adj_py_keys"/"succ_py_keys"/"pred_py_keys" override maps when present.
__setstate__ applies them after the legacy rebuild via new
fnx-classes apply_row_orders methods (leftover-tolerant; adj_indices
mirror rebuilt). DiGraph edges now serialize from inner insertion
order (fixes the random HashMap walk + sparse-mirror drop). Old
pickles (no fields) load exactly as before.

## Proof
- 4-class battery: rows+pred rows+edges(data) round-trip == source ==
  nx round-trip; pickled COPIES keep walk-reordered rows; mixed-key
  display objects survive; native-built grid pickles exactly vs nx.
- 25-trial random mutate corpus, all classes.
- 276 tests (new file + existing view-pickle suite) green;
  full pytest 21565 passed, 0 failed.
