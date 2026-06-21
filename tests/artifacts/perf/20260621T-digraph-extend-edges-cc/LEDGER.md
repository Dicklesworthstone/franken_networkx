# Perf WIN — DiGraph extend_edges_unrecorded: de-dup get_index_of, 0.83x -> 1.04x vs nx (br-r37-c1-digbatch)

- Agent: `BlackThrush` · 2026-06-21 · File: `crates/fnx-classes/src/digraph.rs`
- Executes the DiGraph-construction lever scoped in 4e3def30f.

## The gap
`DiGraph::extend_edges_unrecorded` (backs every DiGraph batch construction:
add_edges_from, conversions, operators, generators) did per edge: contains_key(source) +
contains_key(target) + get_index_of(source)+get_index_of(target) for edge_key + AGAIN
get_index_of(source)+get_index_of(target) for s_idx/t_idx -> ~6 IndexMap hashes/edge. The
simple-Graph sibling already computed each index ONCE. Result: DiGraph.add_edges_from(8000
int edges) = 4.14ms vs Graph 1.04ms, and 0.83x vs nx.

## The fix
Mirror Graph::extend_edges_unrecorded: resolve each endpoint index ONCE via match-insert
(Some(i) => i, None => push node + use len()), reuse for edge_key + the succ/pred push;
self-loop reuses s_idx. Reserve nodes/succ/pred/edges up front from size_hint. Semantics
identical (directed edge_key = (s_idx, t_idx); dedup; succ[s].push(t), pred[t].push(s)).

## Verify
- BYTE-EXACT vs nx 2000/2000 (edges + succ adj order + pred adj order + node order),
  self-loops + duplicate edges correct.
- cargo test extend_edges 3 passed; clippy clean; pytest -k 'digraph/add_edges/construction/
  convert/relabel/union/compose/reverse' 5016 passed.

## MEASURED (nx/fnx, warm min-12)
| case                                  | before | after  |
|---------------------------------------|--------|--------|
| DiGraph.add_edges_from(8000 int edges)| 0.83x (4.14ms) | 1.04x (3.50ms) |

Flipped a loss to a win vs nx; ~15% faster; broad (every DiGraph-returning constructor).
RESIDUAL: DiGraph (3.50ms) is still ~3.4x the simple Graph (1.04ms) for the same edges —
inherent succ+pred (2x) plus a binding-side collect difference; the directed gnm sampler
(reverted in 4e3def30f) can re-land once that residual closes to dominate. Node fast path
(add_nodes_from(range) is Graph-only, DiGraph 0.70 vs 0.08ms) is a separate scoped follow-up.
