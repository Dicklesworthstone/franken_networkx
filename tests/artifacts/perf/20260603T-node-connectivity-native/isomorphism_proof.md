# br-r37-c1-w3yng isomorphism proof

## Change

`global_node_connectivity` now calls `build_node_split_auxiliary(graph)` once and clones that residual template for each `(source, sink)` max-flow probe.

## Proof obligations

- Ordering preserved: yes. Node order, min-degree tie-breaking, neighbor sorting, pair loop order, and `aux_max_flow` neighbor sorting are unchanged.
- Tie-breaking unchanged: yes. The same pair sequence is evaluated; only the residual construction path changes from fresh rebuild to clone of an identical template.
- Floating-point: identical operation domain. Capacities remain `1.0`, `0.0`, and `f64::INFINITY`; `aux_max_flow` receives the same initial capacities for each pair.
- RNG seeds: unchanged. The benchmark graph uses seed `8675309`; production code uses no RNG in this path.
- Graph semantics: unchanged. Self-loop skip and undirected neighbor iteration remain in `build_node_split_auxiliary`.
- Witness values: unchanged for the flow work because the cloned template is structurally equal to a freshly rebuilt residual before each `aux_max_flow` call.
- Golden output: value `4` and digest `bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98` before and after.

## Alien primitive mapping

- Primitive: reuse graph-invariant flow network materialization.
- Source family: graph theory and network-flow artifact compilation from the alien-artifact graph/network-science route.
- Fallback: `git revert` the commit to restore per-pair auxiliary rebuild.
