# Threat Model — fnx-readwrite

## Subsystem Scope
Graph I/O parsers: edgelist, adjacency-list, JSON graph, GraphML, GML.

## Trust Boundary
External input (files, streams, network) → graph data structures. This is the highest-risk trust boundary in the project.

## Threat Categories

### 1. Malformed input / parser abuse
- **Attack:** Crafted files exploiting parser edge cases (nested XML entities in GraphML, unclosed brackets in GML, non-UTF-8 in edgelist, integer overflow in node counts)
- **Impact:** crash (DoS), memory exhaustion, or silent data corruption
- **Current mitigation:** 5 cargo-fuzz targets (one per format) run 30s in CI + 24h nightly; strict/hardened mode fail-closed defaults
- **Residual risk:** fuzz coverage is time-limited; complex multi-stage parse states may have unexplored paths

### 2. Attribute confusion / type abuse
- **Attack:** GraphML attributes with type="string" containing serialized code; GML attributes with extreme nesting; JSON attributes with self-referential structures
- **Impact:** type confusion in downstream algorithms; potential for injection if attributes are ever evaluated
- **Current mitigation:** `CgseValue::parse_relaxed` restricts types to Int/Bool/Float/String; no eval paths exist
- **Residual risk:** custom attribute parsers in future format extensions could reintroduce type confusion

### 3. Resource exhaustion / algorithmic denial
- **Attack:** Files declaring 2^63 nodes or edges; deeply nested XML; circular JSON references
- **Impact:** memory exhaustion, stack overflow, infinite loop
- **Current mitigation:** parser-level limits on node/edge counts; iterative (not recursive) parsing for GML
- **Residual risk:** GraphML parser uses XML crate which may have its own resource limits; need to verify

### 4. Round-trip corruption
- **Attack:** File that parses correctly but serializes differently, causing silent data loss on save
- **Impact:** data integrity violation
- **Current mitigation:** B12 round-trip identity tests (planned); existing edgelist/JSON round-trip fixtures
- **Residual risk:** format-specific lossy conversions (e.g., GraphML namespaces) not yet covered

## Recommended Actions
1. Wire `CgsePolicyEngine` into every parser entry point (D3)
2. Add resource-limit parameters to all parsers (max_nodes, max_edges, max_nesting)
3. Complete B12 round-trip identity tests for all format × graph-type combinations
4. Run 24h nightly fuzz sessions (already in CI G7b for 30s; extend to nightly)
