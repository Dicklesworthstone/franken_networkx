# MST Indexed DSU Rejection (br-r37-c1-7xdf1)

Target: `minimum_spanning_tree` on weighted `gnp_random_graph(1000, 0.01, seed=7)`.

Baseline proof:
- Direct sweep: NetworkX mean `0.014108146875514649s`, FNX mean `0.029337620246224105s`, same golden SHA, FNX/NX ratio `2.0794807783820937`.
- cProfile over 40 FNX calls: wrapper total `0.722s`, `_fnx.minimum_spanning_tree` `0.614s`, native nonfinite scan `0.091s`, attr sync `0.017s`.
- Hyperfine baseline: NetworkX `219.8 ms +/- 10.6 ms`; FNX `469.0 ms +/- 15.8 ms` for graph construction plus five MST calls.

Lever attempted:
- Replace string-keyed `HashMap<&str, &str>` parent/rank union-find in the Rust Kruskal kernel with compact `Vec<usize>` parent/rank arrays and endpoint indexes.
- Preserve node collection order, first-seen undirected edge order, stable weight-only sort, edge orientation, total weight, and result edge order.

Result:
- Golden SHA stayed equal to NetworkX:
  `ae8e326348b0421ee0983a75e74b5a6b282a0d2c092018f43e060c11d2a2fafb`.
- cProfile native section improved only `0.614s -> 0.555s` over 40 calls.
- Hyperfine process envelope regressed: FNX `469.0 ms +/- 15.8 ms -> 686.6 ms +/- 65.9 ms`.

Verdict:
- Rejected. Source hunk was manually reverted; no MST code from this lever was kept.
- Next MST attack should be a deeper primitive, such as combining nonfinite validation with edge/weight collection or replacing the result materialization boundary, not another DSU probe micro-tune.
