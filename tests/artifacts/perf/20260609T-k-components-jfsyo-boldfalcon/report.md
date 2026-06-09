# br-r37-c1-jfsyo - k_components non-forest residual baseline

## Target

Pass 37 baseline/profile pass for true non-forest `k_components` residuals on
`origin/main` `b5d463fc14dbd04a89494df6b8be3bb68d8a289b`. Current FNX has
native certificates for complete graphs, simple cycles, forests, and
clique-block/barbell block graphs. The cases here deliberately miss those
certificates and continue through NetworkX's Moody-White / Kanevsky
`all_node_cuts` path.

Genuine NetworkX comparator: `nx.k_components.orig_func`.

## Golden Proof

- Proof file: `baseline_proof.json`
- Proof SHA256: `c3ef3a8793eb1ee22245e58f0ca658c0b42149957f6488a6329a4382a02e2f3f`
- All FNX outputs match genuine NetworkX canonical output.
- Every proof case trips the `flow_func` sentinel on FNX and genuine NetworkX,
  proving the current fast certificates do not apply.

Golden result SHAs:

| Case | Result SHA256 | Key order |
| --- | --- | --- |
| `square_with_diagonal` | `b74686ef28c51c59bc5911289122723fe778b894b7fbd6afd930ec2f48c85462` | `[2, 1]` |
| `chorded_cycle/12` | `0994c6151bd3f809184ac5a6977abcd76e90e7d83a0e10599b98d2ededc027d8` | `[2, 1]` |
| `chorded_cycle/16` | `f546ac56e7b627d76539490728c9bd9f3f163ab8907fb3b223990a3c36db7b5d` | `[2, 1]` |
| `paired_clique_barbell/8` | `a5701ad4e863ba769bc7ce0890bb71fb3f4cd1035a1d1e52ea4aaff8e9c96caf` | `[7, 6, 5, 4, 3, 2, 1]` |
| `near_barbell_bypass/8` | `7e95f6875d1682b0e16b81a858df6dec2ff66d0d8b2238dbdeb4e2e608b8a95d` | `[7, 6, 5, 4, 3, 2, 1]` |

Ordering/tie-breaking/floating-point/RNG notes:

- Ordering preserved: golden records `k` insertion order and component order;
  FNX matches genuine NetworkX for every residual case.
- Tie-breaking unchanged: no new tie policy is introduced in this pass; all
  measured cases delegate to the residual algorithm.
- Floating point: N/A, outputs are integer node-set structures.
- RNG: N/A, graph builders are deterministic.

## Baseline Timing

Direct in-process timings from `baseline_direct.json`, 3 samples per side:

| Case | FNX mean | NX mean | FNX/NX mean | FNX median | NX median | FNX/NX median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `chorded_cycle/12` | `48.96 ms` | `48.49 ms` | `1.010x` | `48.92 ms` | `48.59 ms` | `1.007x` |
| `chorded_cycle/16` | `644.04 ms` | `625.20 ms` | `1.030x` | `644.12 ms` | `623.67 ms` | `1.033x` |
| `paired_clique_barbell/8` | `14.16 ms` | `13.60 ms` | `1.041x` | `14.09 ms` | `13.70 ms` | `1.028x` |
| `near_barbell_bypass/8` | `22.18 ms` | `21.82 ms` | `1.016x` | `22.07 ms` | `21.87 ms` | `1.009x` |

Hyperfine on `chorded_cycle/16`, 1 warmup and 5 runs:

| Command | Mean | Median | Stddev |
| --- | ---: | ---: | ---: |
| FNX public `k_components` | `1.063 s` | `1.003 s` | `103.9 ms` |
| Genuine NX `orig_func` | `966.99 ms` | `959.62 ms` | `25.5 ms` |

FNX/NX hyperfine ratio: `1.10x` by mean, `1.05x` by median.

## Profile

`baseline_profile_fnx_chorded16.txt`:

- `fnx.k_components` -> `_call_networkx_for_parity`: `1.954 s` cumulative.
- NetworkX `k_components`: `1.952 s` cumulative.
- `networkx.algorithms.connectivity.kcutsets.all_node_cuts`: 59 calls,
  `1.941 s` cumulative, `0.423 s` self.
- `networkx.algorithms.dag.antichains`: 260,896 calls, `1.057 s` cumulative.
- `Graph.__getitem__` / core view access / set updates account for most of the
  remaining cumulative time.

`baseline_profile_nx_chorded16.txt`:

- Genuine NetworkX `k_components`: `1.885 s` cumulative.
- `all_node_cuts`: 59 calls, `1.870 s` cumulative, `0.406 s` self.
- `dag.antichains`: 260,896 calls, `1.013 s` cumulative.
- `edmonds_karp` appears, but only at about `15 ms` cumulative; flow is not the
  dominant frame for this residual.

## Opportunity Matrix

| Lever | Impact | Confidence | Effort | Score | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Native k=2 separation-pair / SPQR-style residual for biconnected non-clique blocks, emitting Moody-White partitions in NetworkX order | 4 | 3 | 4 | `3.0` | Targets the measured `chorded_cycle` residual where `all_node_cuts` + `antichains` dominate. Algorithmically different from prior closed-form certificates. |
| Cache/reuse FNX->NX conversion for delegated residuals | 1 | 4 | 2 | `2.0` | Profile shows only about 70 ms FNX wrapper/conversion delta under cProfile; weak ceiling. |
| Tune flow function/residual-network construction | 1 | 2 | 3 | `0.7` | Flow frames are small on the measured residual; this would miss the current dominant cost. |

Recommended next lever: implement the native k=2 separation-pair residual for
non-clique biconnected blocks, starting with chorded/near-cycle families. Keep
the initial scope to simple undirected `Graph`, integer-node CSR extraction,
NetworkX-order cutset emission, and golden parity against the cases above.

## Command Notes

- `br show br-r37-c1-jfsyo --json` failed in the scratch worktree with
  `ISSUE_NOT_FOUND`; the same command in `/data/projects/franken_networkx`
  showed the bead as `in_progress`.
- `python` was not installed as a command; `python3` was used.
- `py-spy` was not installed; profiling used `cProfile`/`pstats`.
- A broad exploratory stdin timing scout was stopped after running too long on
  oversized residual cases; smaller one-case probes selected `chorded_cycle/16`
  as the hyperfine/profile target.

No source files were edited and no build was needed.
