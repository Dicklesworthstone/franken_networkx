# DiGraph row-flip spec (d58s8 next structural phase)

## Why (measured this session)
DiGraph ctor 2.09x vs Graph 1.46x — DiGraph still carries BOTH String
row families (successors/predecessors IndexMap<String, IndexSet>) that
Graph shed in the P2(c) flip. Its csr() cache derives from the String
rows (String hashing per build); kernels' successors_iter readers walk
them directly.

## Sequencing (phases shippable separately; NO inert scaffolding —
## fields land WITH their writers)
P1: eager succ_indices/pred_indices Vec<Vec<usize>> + ALL writers.
P2: readers (successors/successors_iter/predecessors/csr build).
P3: delete String rows (Graph-flip recipe: delete field, compiler
    enumerates, scoped passes; regexes scoped to the DiGraph impl —
    MultiDiGraph shares field NAMES, the Graph flip's overreach lesson).

## Writer-site map (line numbers at 436c7d4f4; ~22 sites)
- add_node row pair 555-556 -> push Vec::new() x2 when node new
  (guard: succ_indices.len() < nodes.len()).
- add_edge variant A node-creation 754-760 + edge insert 772
  (s_idx/t_idx = get_index_of BEFORE entry-inserts; push t_idx/s_idx
  guarded by edges-newness which the caller checks).
- add_edge variant B 850-875 (same shape).
- extend_nodes 812-813, 915-916 -> push pair per new node.
- extend_edges row stores 951/955 -> indexed pushes.
- remove_node 1090-1091 -> I5 repair both families (Graph recipe:
  outer Vec remove(idx), retain != idx, decrement > idx).
- remove_nodes_from retains 1112/1120 -> removed-mask + remap BEFORE
  shifts (slice-1 recipe).
- ALSO: remove_edge, reverse() (swap succ/pred index vecs!),
  apply_row_orders both variants (operate on indices),
  pickle/setstate builders, clear().
- Phase-1 fields+ctors patch archived here (reverse-applied this
  session; do NOT land without writers — inert-scaffolding
  anti-pattern).

## csr() after P1: build offsets/targets straight from the eager rows
(no String hashing); after P3 maybe csr cache becomes redundant
(slices serve directly) — measure then.
