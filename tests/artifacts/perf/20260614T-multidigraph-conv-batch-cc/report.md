# MultiDiGraph(Graph) conversion — 3.14x slower → 1.56x (2.02x self-speedup)

Bead: br-r37-c1-1o74q (filed this turn)
Agent: cc / 2026-06-14

## Problem (found via exhaustive auto-enumeration scan)

A full warm sweep over every nx single-graph-arg function surfaced two real,
stable, GROWING construction-tax gaps that domain-by-domain scans had missed:
`MultiGraph(g)` ~2.1–2.6x and `MultiDiGraph(g)` ~2.8–3.9x slower than nx when
converting a simple graph to a multigraph.

Root cause: `_copy_constructor_graph_source`'s simple-source→multigraph path fed
`add_edges_from` explicit-key **4-tuples** `(u, v, 0, attrs)`, which bail out of
the native attributed-batch fast-path into the per-edge `add_edge` loop.

## Fix (one lever: 4-tuple → 3-tuple in the undirected→directed-multi expansion)

For `MultiDiGraph(Graph)` (the `expand_undirected_to_directed` case), the source
is simple so each directed endpoint pair appears at most once. Emitting 3-tuples
`(u, v, attrs)` lets the directed-multigraph `add_edges_from` auto-assign key 0
(lowest unused == 0 on a fresh graph) — **byte-identical** to the explicit-key
4-tuple — while routing through the native batch path.

**Scope discipline (verified by interleaved, noise-canceled benching):** the win
is *directed-only*. For undirected MultiGraph targets the symmetric auto-key
lookup makes 3-tuples ~1.5x SLOWER, and `MultiDiGraph(DiGraph)` is ~neutral, so
those paths KEEP the explicit-key 4-tuple. Only the undirected-source→directed-
multi expansion is switched. (A blanket 3-tuple change regressed MultiGraph; the
interleaved test caught it before commit.)

## Proof

- 80-case parity sweep (40 seeds × {undirected, directed source} → {MultiGraph,
  MultiDiGraph}) comparing keyed edges + node attrs + per-node adjacency vs nx —
  **0 mismatches** (all conversion combos, including the unchanged ones).
- Golden (MultiDiGraph from gnp 40,0.15,seed=7, weighted): keyed-edge sha256
  `4ca7a33f7544bbbf…`, stable.
- Full suite: only the 6 known pre-existing failures.

## Timing (interleaved min, N=1000 p=0.02, ~10k undirected edges → ~20k directed)

| op | before (4-tuple) | after (3-tuple) | nx | self-speedup | vs nx |
|----|------------------|-----------------|-----|--------------|-------|
| MultiDiGraph(Graph) | 127.0ms | 63.0ms | 40.5ms | **2.02x** | 3.14x → **1.56x** |

## Residual / follow-up

MultiGraph(g) (~2.1–2.6x) and the remaining MultiDiGraph 1.56x are the multigraph
batch-construction substrate; fully closing them needs a native
`multigraph_absorb_graph` / `multidigraph_absorb_graph_bidirected` kernel
(integer-index space, analogous to the existing `digraph_absorb_graph_bidirected`
for DiGraph(Graph)) — filed as follow-up. Pure-Python lever shipped here.
