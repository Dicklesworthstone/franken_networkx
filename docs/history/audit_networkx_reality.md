# FrankenNetworkX Reality Check Audit

*Generated 2026-04-22 via /reality-check-for-project*

## Executive Summary

FrankenNetworkX has **787 public exports** compared to NetworkX's ~733. All NetworkX
functions are present. Only **2 functions** still delegate to NetworkX at runtime.

## Coverage Breakdown

| Category | Count | % |
|----------|-------|---|
| RUST_NATIVE | 179 | 22% |
| PY_WRAPPER | 584 | 74% |
| NX_DELEGATED | 2 | 0% |
| CLASS | 20 | 2% |
| CONSTANT | 2 | 0% |

## Functions Still Delegating to NetworkX (2)

These are the only functions that call NetworkX at runtime:

1. **`current_flow_closeness_centrality`** - Requires current-flow computation
2. **`edge_current_flow_betweenness_centrality`** - Requires current-flow computation

Both require implementing current-flow algorithms (electrical network solving) in Rust.

## Behavior Parity Gaps (by Family)

### Bipartite Algorithms
- Status: `in_progress`
- Core recognition (`is_bipartite`, `bipartite_sets`) is native
- Gap: Projections and matching-adjacent helpers use Python wrappers

### Community Detection
- Status: `in_progress`
- Native: `louvain_communities`, `label_propagation_communities`, `greedy_modularity_communities`, `modularity`
- Gap: Other community APIs rely on Python-layer implementations

### Graph Utilities / Drawing
- Status: `in_progress`
- Native: Basic layout helpers (`circular_layout`, `random_layout`, `shell_layout`, `rescale_layout_dict`)
- Gap: Some drawing text/raw-rendering helpers still delegate through NetworkX conversion

### Algorithm Core (280+ native)
- Status: `in_progress`
- Gap: Current-flow family (electrical network solving)

## Mock/Stub Findings (2)

From /mock-code-finder scan:

1. `fnx-algorithms/src/test_dijkstra.rs:11` - `assert!(false)` debug test
2. `fnx-conformance/src/lib.rs:2336` - Topological sort placeholder

## High-Impact [REALITY-CHECK] Beads

| Priority | Item | Impact | Effort |
|----------|------|--------|--------|
| P0 | current_flow_closeness_centrality | Last NX delegate | High |
| P0 | edge_current_flow_betweenness_centrality | Last NX delegate | High |
| P1 | Bipartite projection native impl | Common use case | Medium |
| P1 | Community detection expansion | Analytics workloads | Medium |
| P2 | Drawing text helpers native | Visualization | Low |

## Bead Commands (for manual filing)

```bash
# P0: Last NX delegates
br create "[REALITY-CHECK] Native current_flow_closeness_centrality - last NX delegate"
br create "[REALITY-CHECK] Native edge_current_flow_betweenness_centrality - last NX delegate"

# P1: High-impact native conversions
br create "[REALITY-CHECK] Native bipartite projection (bipartite.projected_graph)"
br create "[REALITY-CHECK] Native bipartite collaboration_weighted_projected_graph"
br create "[REALITY-CHECK] Native community asyn_lpa_communities"

# P2: Drawing parity
br create "[REALITY-CHECK] Native draw_networkx text rendering helpers"
```

## Conclusion

FrankenNetworkX has achieved near-complete API coverage. The remaining gaps are:
- 2 current-flow functions (require linear algebra solver in Rust)
- Behavior parity refinements (Python wrappers need native replacement)

No missing functions from NetworkX.__all__.
