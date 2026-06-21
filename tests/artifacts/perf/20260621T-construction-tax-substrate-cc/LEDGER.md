# VERIFICATION + NEGATIVE EVIDENCE — relabel/BA construction-tax is String-keyed-substrate bound (eager-alloc theory ruled out)

- Agent: `BlackThrush` · 2026-06-21 · MEASURED

## Sweep (this turn): shortest-paths / DAG / products / generators / conversions — all WIN
floyd_warshall 14.8x, astar 8.35x, johnson 1.83x, bellman_ford 1.91x, lexico_topo_sort 3.12x,
transitive_reduction 1.81x, dag_longest_path 2.47x, topological_generations 2.07x,
cartesian_product 2.98x, tensor_product 4.64x, complement 3.12x, line_graph 3.86x,
convert_node_labels_to_integers 6.85x, stochastic_graph 4.73x, to/from_scipy 1.46x/1.86x,
random_regular 2.63x, random_geometric 1.23x, powerlaw_cluster 1.11x.

## The 2 residual losses — both KNOWN/BOUNDED
- relabel_nodes 0.72x (212us vs nx 153us). barabasi_albert_graph 0.76x.

## relabel PROFILE (pinpoints the bound + rules out a theory)
- G.edges() materialize 25.5us | remap list-comp 35us | **build (add_nodes_from + add_edges_from)
  165.8us** | _native_graph_has_any_attrs gate 0.1us. The BUILD alone (165us) exceeds nx's
  ENTIRE relabel (153us).
- RULED OUT (negative evidence): the build is NOT eager-empty-PyDict alloc — both node and
  edge attrs already use lazy `materialize_{node,edge}_py_attrs` (`or_insert_with`), so the
  br-r37-c1-w1dm8 lazy-attr-dict lever is already DONE for this path. The 165us is the
  String-keyed node-construction substrate: node_key_to_string canonicalization + the
  per-node/edge IndexMap inserts + node_key_map. That's the same wall as the native
  clone+rename relabel attempt (reverted, parity-bound by per-node label PyO3 round-trips).
- barabasi_albert already batches (single add_edges_from); residual is RNG-parity-faithful
  sampling (must reproduce nx's PythonRandom draw sequence) + the same construction substrate.

## Conclusion
relabel/BA/convert construction is bound by the String-keyed node-construction substrate, not
by a wrapper inefficiency or an eager alloc. The lever is the node-keying / int-CSR substrate
(bead yl606-class), not a my-file Python change. No ship; comprehensive domination otherwise.
