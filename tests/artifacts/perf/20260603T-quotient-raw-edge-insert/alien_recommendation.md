# Alien primitive: trusted bulk boundary bypass

Bead: `br-r37-c1-04z53.43`

Profile signature: after the quotient node-metrics and public batch-boundary
passes, cProfile still leaves `quotient_graph` dominated by the internal
default edge insertion boundary. The generated `edge_bunch` is already a
trusted list of 2- or 3-tuples, so the public `Graph.add_edges_from` wrapper's
shape/hashability/partial-generator guards are redundant on this path.

Graveyard match:

- `alien_cs_graveyard.md` bulk-operation optimization: callers must supply a
  batch of independent lookups/inserts for the bulk path to pay off.
- `high_level_summary_*` stable boundary doctrine: keep a stable public
  boundary, but let hot internal paths cross a narrower validated internal
  boundary when the proof obligations are explicit.

Artifact coding obligations:

1. The generated edge batch must be a concrete `list`, never a generator.
2. Every edge must be a tuple with hashable block endpoints already present as
   nodes in `H`.
3. Weighted edges must carry a fresh attribute dict with the same aggregate
   value as the public path.
4. The block-pair loop order must not change.
5. All custom relation/data, directed, multigraph, explicit `create_using`,
   and unsupported-weight cases stay on the previous public/fallback path.
