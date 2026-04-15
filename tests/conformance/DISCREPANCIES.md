# Known Conformance Divergences

This document tracks intentional behavioral divergences between FrankenNetworkX
and the upstream NetworkX reference implementation.

## Status: No Intentional Divergences

As of the last conformance run, FrankenNetworkX has **zero** intentional
divergences from NetworkX behavior for the scoped V1 API surface.

The conformance harness (`fnx-conformance`) validates 78+ fixtures covering:
- Shortest path algorithms (BFS, Dijkstra, Bellman-Ford, multi-source)
- Connectivity (components, bridges, articulation points)
- Centrality (degree, closeness, betweenness, eigenvector, PageRank, HITS, Katz)
- Clustering (coefficient, triangles, square clustering)
- Matching (maximal, max-weight, min-weight)
- Flow (max flow, min cut, edge connectivity)
- Tree/forest detection
- Euler path/circuit
- Bipartite detection
- Graph generators
- Read/write (JSON, edge list, adjacency list, GraphML)

## Divergence Categories

When divergences are discovered, they will be documented here with:
- **DISC-NNN** sequential ID
- **Acceptance status**: ACCEPTED, INVESTIGATING, or WILL-FIX
- **Affected tests**: Which fixtures or test cases
- **Resolution**: Why it's acceptable or how it will be fixed
- **Review date**: When the divergence was last evaluated

### Hardened Mode Allowlists

FrankenNetworkX supports two compatibility modes:
- **Strict mode**: Behavior must match NetworkX exactly
- **Hardened mode**: Safety guards may modify behavior for malformed inputs

No hardened-mode allowlisted divergences exist currently.

## Conformance Artifacts

The conformance harness generates reports at:
- `artifacts/conformance/latest/smoke_report.json` - Full fixture results
- `artifacts/conformance/latest/structured_logs.jsonl` - Per-test traces
- `artifacts/conformance/latest/*.report.json` - Per-fixture detailed reports

Run conformance tests with:
```bash
rch exec -- cargo run -p fnx-conformance --bin run_smoke
```

## Adding New Divergences

When a divergence is identified:
1. Assign a DISC-NNN ID
2. Document the reference behavior vs. our behavior
3. State the acceptance status with rationale
4. List affected test fixtures
5. If ACCEPTED, add to hardened allowlist if appropriate
6. Update the conformance harness to use XFAIL (not SKIP)
