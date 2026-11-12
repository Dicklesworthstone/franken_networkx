# bfs_tree indexed result construction benchmark report

Bead: `br-r37-c1-04z53.38`

Date: 2026-06-03

Agent: `TealSpring`

## Profile-backed target

The patched residual traversal sweep identified `bfs_tree` as the largest matching-hash traversal residual:

- FNX mean: `0.007274535446777008s`
- NetworkX mean: `0.00473990044411039s`
- Shared SHA: `1080bb4f9f5cb05745326b002917767f0f0693de81f277c7cb6df03e49d14b76`

Pass-local baseline:

- FNX direct repeat-50 mean: `0.007129831201164052s`
- NetworkX direct repeat-50 mean: `0.004709167139953934s`
- Shared SHA: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`
- Hyperfine baseline mean: `0.43992501238666665s`
- cProfile: native `_fnx.bfs_tree` was `0.357s` cumulative over 50 calls.

## Candidate lever

Add an undirected simple-Graph `bfs_tree` path that:

- Computes BFS tree edges as node indices.
- Builds the returned `PyDiGraph` directly from those indices.
- Avoids materializing and then cloning an intermediate `Vec<(String, String)>` edge stream.

Directed, reverse, sorted-neighbor, and fallback paths were left unchanged.

## Candidate result

Direct repeat-50 sample:

- Candidate FNX mean: `0.006317437958787195s`
- Candidate speedup vs baseline direct mean: `1.13x`
- Candidate SHA: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`

Hyperfine:

| Run | Mean | Stddev | Median |
| --- | ---: | ---: | ---: |
| Baseline | `0.43992501238666665s` | `0.019488278227717596s` | `0.44234449712s` |
| Candidate | `0.43277942618s` | `0.02702110508881706s` | `0.43505407078s` |
| Candidate confirm | `0.43308385356000006s` | `0.025742177641093954s` | `0.42553591716000005s` |

The process-level improvement is only about `1.016x`, with overlapping noise. This does not meet the campaign keep bar.

## Score

Impact 1 x Confidence 2 / Effort 3 = `0.67`.

Verdict: rejected. Candidate source was manually removed and the release extension was rebuilt from restored source.

