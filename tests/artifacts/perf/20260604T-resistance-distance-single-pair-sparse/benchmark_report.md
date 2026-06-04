# resistance_distance single-pair sparse reduced-Laplacian solve

Bead: `br-r37-c1-resistance-distance-single-pair-pinv-bdr8q`

## Profile-backed target

The old pair form built the full dense Laplacian pseudo-inverse even though a
single scalar effective resistance only needs one grounded reduced-Laplacian
solve.

Dense baseline profile (`profile_dense_exact_baseline.txt`, 2 repeats):

```text
4.331 s total
4.178 s in numpy.linalg.pinv
4.117 s in numpy.linalg.svd/eigh
```

That is the profile-backed target: full dense `pinv(L)` for a scalar read.

## Lever

For `nodeA is not None and nodeB is not None`, compute:

```text
r(i,j) = (e_i - e_j)_red^T L_red^{-1} (e_i - e_j)_red
```

where `L_red` drops one grounded node from the same sparse Laplacian matrix.
Failures fall back to the existing dense path. Single-endpoint and all-pairs
return shapes still use dense `L^+`.

## RCH benchmark results

Same-process sweep, 5 repeats per row:

```text
case                         before fnx mean   after fnx mean   speedup
unweighted_sparse_pair       2.309381909 s     0.042322646 s    54.6x
weighted_sparse_pair         1.034490122 s     0.025957141 s    39.9x
weighted_multigraph_pair     1.442183850 s     0.999485298 s     1.4x
```

Process-level hyperfine on the unweighted sparse pair command shape:

```text
dense exact baseline mean    3.470474029 s
current FNX mean             0.456218071 s
process-level speedup        7.6x
```

The MultiGraph weighted case still spends substantial time in graph copy and
weight inversion before the solve; the simple sparse Graph pair forms are the
primary bead target and show the expected complexity-class win.

## Score

Impact: 7.6x hyperfine process-level win and 39.9x to 54.6x same-process pair
win on the targeted sparse Graph cases.

Confidence: 0.96. Golden JSON is byte-identical before/after, embedded digest
matches current FNX, dense exact, and NetworkX, and 73 focused parity tests
pass.

Effort: 1.0. One algorithmic lever in `resistance_distance` plus artifact
harness and proof files.

Score: `Impact x Confidence / Effort = 7.6 * 0.96 / 1.0 = 7.30`, keep.
