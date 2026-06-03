# Alien Recommendation Card: Top-Level adjacency_data Native Delegate

## Symptom

The json_graph submodule already used `_fnx.adjacency_data_simple`, but top-level `fnx.adjacency_data` still walked `G.adj[node]` through Python view machinery. Baseline cProfile for 30 directed calls spent `1.782s` in `adjacency_data`, dominated by `AtlasView` accessors and lambda wrappers.

## Primitive

Use the already-shipped safe-Rust bulk serialization primitive as a zero-copy-style boundary reduction: one native call builds the `nodes` and `adjacency` arrays, copying Python attr dicts and appending the `id_` field in the same order as the Python wrapper.

## Score

| Impact | Confidence | Effort | Score |
|---:|---:|---:|---:|
| 4 | 5 | 1 | 20.0 |

Decision: keep. The native delegate removes the profiled Python view walk, preserves exact output SHA, and improves direct call means by more than 4x.
