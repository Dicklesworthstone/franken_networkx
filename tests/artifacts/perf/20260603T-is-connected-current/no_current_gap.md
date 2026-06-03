# is_connected BA5000 no-current-gap proof

Bead: `br-r37-c1-04z53.19`

Reason for target:
- Prior public residual sweep showed `is_connected_ba_5000` digest match with fnx mean 0.0032156744294167894 s and NetworkX mean 0.0015190009996461282 s.

Fresh current-HEAD baseline:
- Harness: `bench_is_connected.py`.
- Workload: BA(5000,4,seed=42), 5000 nodes, 19984 edges.
- Golden sha256: `78886afa924c59ae65667c7694275e4217e5ff0db770192e387f957da67e5852`.
- fnx sampled mean: 0.00011697059962898493 s.
- fnx sampled median: 0.00010349599324399605 s.
- NetworkX sampled mean: 0.0015528898991760797 s.
- NetworkX sampled median: 0.0014224434999050573 s.
- Current fnx is 13.276x faster by sampled mean.

Profile:
- `profile_fnx.txt` shows 10 calls spend about 0.001 s total, entirely in `_fnx.is_connected`.
- Python wrapper overhead is not a material hotspot.

Verdict:
- No source change. The old residual gap is stale at current HEAD.
- Score: Impact 0 x Confidence 5 / Effort 1 = 0.0.
- Close this bead as no-current-gap and reprofile the next residual target.
