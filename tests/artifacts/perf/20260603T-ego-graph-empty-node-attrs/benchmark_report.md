# ego_graph empty node attrs benchmark report

Bead: br-r37-c1-04z53.32

Baseline:
- FNX sample mean: `0.0242919315972055s`
- NetworkX sample mean: `0.021780150699972484s`
- Hyperfine mean: `0.6794944671333334s`

After candidate:
- FNX sample mean: `0.02533302050239096s`
- Hyperfine mean: `0.6558192539333335s`

Delta:
- Direct sample speedup: `0.9589x` (regression)
- Hyperfine speedup: `1.0361x`

Gate decision:
- Rejected. The direct target measurement regressed and the hyperfine-only delta was below Score >= 2.0.
