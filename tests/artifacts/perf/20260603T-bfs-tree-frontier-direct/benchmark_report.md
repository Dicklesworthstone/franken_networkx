# Edge-View Fail-Fast Seq-Counter Guard

Bead: `br-r37-c1-epg5e`

## Target

Profile-backed target came from the `bfs_tree` observed-output harness on `barabasi_albert_graph(3000, 4, seed=42)`.

Raw `bfs_tree()` construction remained a residual gap:

- FNX: `0.006609352779341862s`
- NetworkX: `0.004509331518784165s`
- Golden SHA: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`

The cProfile showed the returned `DiGraph` edge observation path dominating golden-output normalization:

- `_FailFastEdgeIterator.__next__`: `0.681s` over 150000 edges.
- `DiGraph.number_of_edges`: `0.438s` over 150000 calls.
- `_has_networkx_private_storage` / `_private_override`: `0.339s` / `0.320s`.

The earlier direct BFS indexed-result builder was already rejected, so this pass targeted the observed-output edge-view guard rather than another BFS traversal micro-lever.

## Lever

Use existing Rust mutation sequence counters in `_FailFastEdgeIterator`:

- Native graphs without NetworkX private storage snapshot `nodes_seq`.
- Edge-count-guarded iterators also snapshot `edges_seq`.
- `__next__` compares sequence counters instead of calling `len()` and `number_of_edges()` per edge.
- Non-native/private-storage fallback remains the old count-based guard.

This is one lever: replace per-edge count scans with O(1) mutation-counter checks on the native no-private-storage path.

## Results

Raw `bfs_tree()` construction sample, 50 repeats:

| Metric | Baseline | After | Decision |
| --- | ---: | ---: | --- |
| FNX mean | `0.006609352779341862s` | `0.006662167000467889s` | neutral/no keep claim |
| FNX SHA | `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` | `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64` | unchanged |

Observed-output cProfile, 50 repeats:

| Frame | Baseline cumulative | After cumulative |
| --- | ---: | ---: |
| Total profile | `1.875s` | `1.169s` |
| `normalize` | `0.992s` | `0.312s` |
| `_FailFastEdgeIterator.__next__` | `0.681s` | `0.043s` |
| `DiGraph.number_of_edges` inside guard | `0.438s` | absent from top 80 |
| `_has_networkx_private_storage` | `0.339s` | absent from top 80 |

Hyperfine observed-output envelope, 25 runs:

| Metric | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| Mean | `0.6330912347600001s` | `0.58701323932s` | `1.078x` faster |
| Median | `0.6282573156800001s` | `0.58331325396s` | `1.077x` faster |
| Min | `0.5924780526800001s` | `0.53620055696s` | `1.105x` faster |

## Score

Impact `2` x Confidence `4` / Effort `2` = `4.0`.

Keep decision: retained for the edge-view observed-output path. The patch is not claimed as a raw `bfs_tree()` construction win; the next BFS construction primitive still needs to attack native tree construction or result representation.

## Artifacts

- Baseline FNX sample: `baseline_bfs_tree_fnx.jsonl`
- Baseline NX sample: `baseline_bfs_tree_nx.jsonl`
- After FNX sample: `after_bfs_tree_fnx.jsonl`
- Baseline profile: `profile_baseline_bfs_tree_fnx.txt`
- After profile: `profile_after_bfs_tree_fnx.txt`
- Baseline hyperfine: `hyperfine_baseline_bfs_tree_fnx.json`
- After hyperfine: `hyperfine_after_bfs_tree_fnx.json`
