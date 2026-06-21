# MEASURED warm bench of this session's code-only de-delegations (br-r37-c1-measuredbatch)

- Agent: `BlackThrush` · 2026-06-20 · warm min-of-12 (warmup 5), `taskset -c 2 PYTHONHASHSEED=0`,
  existing install (Python-only changes; .so unchanged). nx/fnx ratio = nx_time / fnx_time
  (>1 = fnx WINS).

## CONFIRMED WINS (fnx > nx)
| function                         | nx/fnx | note |
|----------------------------------|--------|------|
| threshold_graph                  | 3.10x  | int-CSR Graph, big win |
| complete_bipartite_graph(60,60)  | 1.90x  | Graph |
| from_prufer_sequence(n=50)       | 1.84x  | Graph |
| random_graph(80,80,0.3) undir    | 1.50x  | Graph |
| transitive_reduction(n=60)       | 1.19x  | DiGraph, skip 2x conversion |
| random_k_out_graph(100,4)        | 1.09x  | MultiDiGraph, numpy-repro ~neutral |

## fnx < nx but de-delegation is the BEST fnx option (NOT regressions — do NOT revert)
For each, my native build is FASTER than the prior delegated path (nx-build +
_from_nx_graph), but fnx still loses to PURE nx due to the substrate:
| function               | nx/fnx | native vs deleg | root cause |
|------------------------|--------|-----------------|------------|
| projected_graph DIR    | 0.64x  | native 0.647ms < deleg 1.539ms (2.4x better) | DiGraph snapshot + Python set-comp algo overhead vs nx |
| gnmk_random_graph      | 0.89x  | native faster   | Graph; rng.choice rejection-loop Python overhead |
| havel_hakimi_graph     | 0.52x  | native 0.330ms < deleg 0.558ms | String-keyed MultiGraph substrate (add_edges_from slow) |
| configuration_model    | 0.42x  | native 0.695ms < deleg 0.796ms | String-keyed MultiGraph substrate |

CONCLUSION: keep all de-delegations (each beats its delegated alternative). The fnx<nx
residual on MultiGraph-returning generators is SUBSTRATE-BOUND — the String-keyed
multigraph storage (3x, slow add_edges_from) needs the int-CSR migration (Rust, beads
br-r37-c1-yl606); the directed-projection residual is Python-algorithm overhead. Neither
is fixable code-only. NOT reverted (reverting -> the slower delegated path).

## Method note (re-affirms the MEASURED discipline)
Code-only de-delegations LOOK like wins (skip conversion) but for slow-substrate result
types they can be fnx<nx — only a warm head-to-head reveals it. Confirmed they still beat
the delegated alternative, so they stand. The deferred-bench backlog was right to defer:
~half the bipartite-generator wins are substrate-capped, not clean wins.
