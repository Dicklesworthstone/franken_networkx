# BFS Neighbor-Iterator Optimization Delta

Single optimization lever: eliminate per-call neighbor `Vec` allocation in traversal paths by using iterator/count APIs on `Graph`.

| Metric | Pre (ms) | Post (ms) | Delta (ms) | Delta (%) |
|---|---:|---:|---:|---:|
| mean_ms | 246.320693 | 244.636782 | -1.683911 | -0.684% |
| p50_ms | 246.955860 | 243.969523 | -2.986336 | -1.209% |
| p95_ms | 249.507865 | 250.956755 | +1.448889 | +0.581% |
| p99_ms | 249.554883 | 251.342389 | +1.787506 | +0.716% |
| min_ms | 237.529612 | 237.888177 | +0.358566 | +0.151% |
| max_ms | 249.566638 | 251.438797 | +1.872160 | +0.750% |

Interpretation:
- Central tendency improved (mean and p50).
- Tail metrics regressed slightly in this sample window, so the lever should be retained only with continued p95/p99 tracking in CI.
