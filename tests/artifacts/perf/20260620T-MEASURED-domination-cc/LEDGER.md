# MEASURED domination scorecard — algorithm + I/O surface (br-r37-c1-measuredom)

- Agent: `BlackThrush` · 2026-06-20 · warm min-of-10 pinned (`taskset -c 2 PYTHONHASHSEED=0`),
  existing install, G = gnm_random_graph(300, 900). nx/fnx = nx_time/fnx_time (>1 = fnx WINS).

## fnx DOMINATES — every benched algorithm/IO fn is a win or neutral (0 losses)
| function               | nx/fnx |
|------------------------|--------|
| clustering             | 50.48x |
| square_clustering      | 23.60x |
| core_number            |  9.70x |
| triangles              |  6.46x |
| degree_centrality      |  3.46x |
| to_scipy_sparse_array  |  2.44x |
| node_link_data         |  1.95x |
| pagerank               |  1.51x |
| adjacency_data         |  1.27x |
| to_numpy_array         |  1.18x |
| generate_edgelist      |  1.17x |
| generate_adjlist       |  1.05x (neutral) |

## Session-wide MEASURED conclusion
Across generators (batch1), redundant-conversion + projections (batch2), view-
materialization (views), and now algorithm/IO (this sweep), the ONLY measured fnx<nx
cases are SUBSTRATE-BOUND:
  1. MultiGraph-returning generators (havel_hakimi 0.52x, configuration_model 0.42x) —
     String-keyed multigraph storage; int-CSR migration br-r37-c1-yl606 (Rust).
  2. edge-attr view materialization (get_edge_attributes 0.72x) — persistent edge-attr
     mirror (Rust).
  3. directed bipartite projection (0.64x) — Python-algo overhead, best-fnx-option.
Every one is still the best fnx option (beats its delegated alternative) -> none reverted.
Everything else MEASURED is a clean fnx win. The code-only + warm-bench surface is
DOMINATED; remaining gaps need a cold rebuild (disk-blocked).
