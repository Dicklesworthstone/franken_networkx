# CGSE Witness Artifacts

Per-algorithm-family complexity witness artifacts. Each execution of a CGSE-instrumented algorithm can emit a `ComplexityWitness` that proves which tie-break decisions were made.

## Directory Structure

```
witnesses/
  shortest_path/     # dijkstra, bellman_ford
  traversal/         # bfs, dfs
  matching/          # max_weight_matching, min_weight_matching
  connectivity/      # connected_components, strongly_connected_components
  trees/             # kruskal, prim
  euler/             # eulerian_circuit
  dag/               # topological_sort
```

## Witness Record Schema

Each witness is a JSON object:

```json
{
  "n": 100,
  "m": 200,
  "dominant_term": "n_plus_m_log_n",
  "observed_count": 42,
  "policy": "weight_then_lex",
  "seed": null,
  "decision_path_blake3": "abc123..."
}
```

### Fields

- `n`: Number of nodes in the input graph
- `m`: Number of edges in the input graph  
- `dominant_term`: Complexity class symbol (e.g., "n_plus_m", "n_m", "m_log_m")
- `observed_count`: Number of tie-break decisions recorded
- `policy`: The TieBreakPolicy id governing the execution
- `seed`: Optional RNG seed for randomized algorithms
- `decision_path_blake3`: 32-byte Blake3 hash (hex) over ordered tie-break decisions

## Usage

Witnesses can be collected during conformance testing:

```rust
use fnx_cgse::collect_witnesses;

let (result, witnesses) = collect_witnesses(|| {
    dijkstra(&graph, "a", "weight")
});

for w in witnesses {
    println!("Hash: {}", hex::encode(w.decision_path_blake3));
}
```

From Python:

```python
import franken_networkx as fnx

# Access CGSE metadata
policy = fnx._fnx.cgse.algorithm_policy("dijkstra")
print(policy.id())  # "weight_then_lex"

registry = fnx._fnx.cgse.policy_registry()
print(registry["dijkstra"]["dominant_complexity"])  # "n_plus_m_log_n"
```

## Witness Verification

Two executions on the same graph with the same policy should produce identical `decision_path_blake3` hashes. Hash mismatches indicate ordering drift.
