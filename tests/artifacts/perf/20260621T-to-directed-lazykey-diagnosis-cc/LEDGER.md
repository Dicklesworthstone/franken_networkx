# DIAGNOSIS (refines 435776579) — to_directed/to_undirected attr-drop is the lazy INT-display-key divergence (qq6hi)

- Agent: `BlackThrush` · 2026-06-21

## Precise trigger (isolated this turn)
to_directed()/to_undirected() drop edge attrs ONLY for:  INT nodes + `add_edges_from` batch.
  A) add_edges_from(int 3-tuples)            -> DROP (0/222)
  B) add_nodes_from(int)+add_edges_from      -> DROP (0/222)
  C) fnx.Graph(int 3-tuples) constructor     -> OK (222/222)
  D) per-edge add_edge(int)                  -> OK
  E) add_edges_from with STRING nodes        -> OK (222/222)
So it is NOT general batch construction (last turn's guess) — it is the INT-NODE lazy
display-key path specifically.

## Mechanism
This is the known lazy-int-display-key divergence (bead qq6hi P1, reference_lazy_key_canonical_
divergence). For int/range nodes the DISPLAY key (int 0) diverges from the CANONICAL str key
("str:1:0"). The add_edges_from batch on int nodes leaves the edge attrs reachable via
edges(data=True)/get_edge_data (which resolve the display key) but NOT via edges_ordered()
(self.edges/edge_index_endpoints by index) NOR the edge_py_attrs mirror keyed by the canonical
str form that to_directed builds from edges_ordered names -> both lookups miss -> empty attrs.
Any prior materializing read reconciles the key forms and fixes it.

## Why my 3 fixes failed (all reverted)
edges_ordered self.edges.iter(), to_directed inner.edge_attrs(name), to_undirected mirror-or-
snapshot.attrs ALL read empty because the int-batch attrs aren't in the index/canonical-keyed
structures those touch — they're only reachable through the display-key resolution that
edges(data=True) performs. The fix belongs in the lazy-key substrate (qq6hi), not the
conversion layer. constructor (C) populates differently, so it works — a possible reference
for aligning the add_edges_from int path.
