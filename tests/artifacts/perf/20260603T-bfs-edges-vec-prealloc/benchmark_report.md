# bfs_edges Vec preallocation benchmark report

Bead: br-r37-c1-04z53.31

Baseline:
- FNX sample mean: `0.006757828120607883s`
- NetworkX sample mean: `0.004501300221891142s`
- Hyperfine mean: `0.6238517696533332s`

After candidate:
- FNX sample mean: `0.006814447081414983s`
- Hyperfine mean: `0.6064132063333333s`

Delta:
- Direct sample speedup: `0.9917x` (regression)
- Hyperfine speedup: `1.0288x`

Gate decision:
- Rejected. The direct target measurement regressed and the hyperfine-only win was below the confidence/score bar.
