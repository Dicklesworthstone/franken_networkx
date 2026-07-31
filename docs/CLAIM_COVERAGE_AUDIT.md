# Claim coverage audit — how much of our claimed ground rests on an incumbent comparison

**Date:** 2026-07-31 · **Auditor:** BlackThrush (cc) · **HEAD:** `629268633`
**Trigger:** fleet policy — a perf KEEP requires a vs-incumbent ratio. frankenfs audited itself
and found 67 of 186 KEEP claims carried none. This is the same audit run here.
**Scope:** inventory, plus the first converted claim. No claim is deleted by this document.

## Headline

Of **591** KEEP claim rows across the three active ledgers, **12** carry a vs-incumbent ratio
measured with NetworkX live in the same invocation, and **579** do not — **2.0%** attested
coverage. Our position is substantially worse than frankenfs's (they were missing 36%; we are
missing 98%).

Reproduce with `python3 scripts/perf_ledger_preflight.py --audit`. Those counts are the pre-commit
state of this session; the three ledger rows landed below add 9 converted claims and move the
attested count to 15.

Also: **39 of 591** carry the in-process loaded-ELF SHA-256; **552** do not.

## Cannot-convert vs not-yet-measured

The fleet policy asks that claims which *cannot* be converted — because no incumbent arm exists
for the surface — be separated from claims nobody has yet measured. They are different problems.

| Class | Rows | Convertible? |
|---|---:|---|
| Attested `INCUMBENT` — live nx, same invocation | 12 | already done |
| Declared `SELF-SPEEDUP` — fnx-before vs fnx-after | 2 | **no** — no incumbent counterpart exists by construction |
| No numeric ratio at all (note/milestone rows) | 9 | **no** — nothing to convert |
| Ratio present, vs-nx wording in the row | 259 | yes — not yet measured |
| Ratio present, no vs-nx wording in the row | 309 | yes — not yet measured |

So: **11 rows genuinely cannot be converted**, and **568 are simply unmeasured**. There is no
large "unmeasurable" bucket to hide behind.

### Correction to the 2026-07-30 revision of this document

The previous revision split the unattested rows into "~203 plausibly convertible" and "~365
self-speedup shaped", implying most of the ledger was maintenance rather than competitive claims.
**That split was wrong**, and it flattered us.

The repo's ratio convention is `ratio = t_nx / t_fnx` (`scripts/perf_harness.py:799-805`: "with
arm_a = networkx and arm_b = franken_networkx this reads as 'fnx is Nx faster', matching the
ledger convention"). Under that convention a bare row like `MDG out_edges 0.34x->0.57x` is a
**vs-NetworkX** claim — a loss against nx being narrowed — not a self-speedup. Those 309 rows are
competitive claims that merely omit the word "networkx", so they belong in the convertible bucket.
Only the 2 rows that *declare* `comparison_class=SELF-SPEEDUP` are genuinely non-competitive.

## Converted this session — 10 claims attempted, 9 decidable

**7 of the 9 decidable claims excluded their published figure**, in both directions. Two were
confirmed. One claim was refused outright by the null gate. The table is *stale*, not
systematically inflated in our favour.

| Claim | Published | Measured on HEAD | CI | Verdict |
|---|---:|---:|---|---|
| `k_crust` | 5.8664× | **13.2556×** | `[13.0197, 13.4719]` | understated 2.26× |
| `erdos_renyi_graph` (n=1500) | 14.1755× | **12.87–13.15×** | `[12.7466, 12.9737]` / `[12.9774, 13.2413]` | overstated ~9% |
| `single_source_shortest_path_length` | 5.5005× | **5.1868×** | `[5.1226, 5.2776]` | overstated 6.1% |
| `kosaraju_strongly_connected_components` | 4.6519× | **4.8474×** | `[4.7558, 4.8640]` | understated 4.2% |
| `to_scipy_sparse_array` | 2.4073× | **2.4758×** | `[2.4292, 2.5547]` | understated 2.8% |
| `dfs_successors` | 2.1456× | **2.3223×** | `[2.2986, 2.3523]` | understated 8.2% |
| `label_propagation_communities` | 2.1485× | **2.1827×** | `[2.1643, 2.2244]` | understated 1.6% |
| `pagerank` | 2.6361× | 2.7275× | `[2.5777, 2.8818]` | **CONFIRMED** |
| `partition_spanning_tree` | 2.4612× | 2.3794× | `[2.3303, 2.5633]` | **CONFIRMED** |
| `minimum_branching` | 3.9768× | 3.9978× | `[3.8395, 4.1784]` | **UNDECIDABLE** — null bias 0.0295 |

All decidable rows: `21/21` wins, byte-identical canonical output against live NetworkX 3.6.1
proven in the same invocation before timing. Ledger rows: `br-r37-c1-p80x1.1`, `.5`, `.7`, `.9`,
`.13`, `.21`, `.23`, `.25`, `.27`, `.29`.

`minimum_branching` is the gate working: it produced a plausible `3.9978×` with 21/21 wins, but the
A/A NetworkX null drifted to median `1.0295`, breaching the third clause. A two-clause gate would
have banked a bogus confirmation. Recording contention instead of pre-refusing it does **not**
lower the bar — the gate still refuses when the environment actually perturbs the comparison.

### `erdos_renyi_graph` (n=1500) — README's highest-ranked unconverted claim

Ranked by public exposure, not by ease. Result:

| | Published | Measured on HEAD |
|---|---:|---|
| Run A (`taskset -c 0-31`) | 14.1755× | **12.8702×** CI `[12.7466, 12.9737]` |
| Run B (`taskset -c 32-63`) | 14.1755× | **13.1460×** CI `[12.9774, 13.2413]` |

Both runs DECIDABLE under the corrected three-clause median gate; both **exclude** the published
figure, which sits 9.3% above run A's upper CI bound. The claim remains a large win; the specific
published number was overstated and has been corrected in `README.md` to `12.87–13.15×`.

Attestation: live NetworkX 3.6.1 in the same invocation; byte-identical canonical output
(SHA-256 `93fcf9ae…`) proven before timing; in-process loaded-ELF SHA-256
`e5bb3755812c732b63bb8ab3e4650d526bb69bb67834d264f8b00adfad4a3213`; host identity
`thinkstation1`; actual observed threads `1` for **both** arms. Full row in
`docs/NEGATIVE_EVIDENCE.md` under `br-r37-c1-p80x1.1`.

The binary was rebuilt at HEAD first — the `site-packages` install was 44 Rust commits stale, so
any ratio taken against it would have been invalid.

## Root cause of the 19 remaining unconverted README rows — corrected

Every prior `p80x1.*` row recorded NO-VERDICT and attributed the blockage to RCH minting a
per-invocation Cargo target directory. **That diagnosis was wrong.** `CARGO_TARGET_DIR=/data/tmp/cargo-target`
is honoured across `rch exec --base <commit> --clean-overlay --no-overlay` and is independent of
the UUID-salted remote source root; the HEAD build this session used it with no new directory.

The actual binding constraint is `require_host_wide_quiescence`
(`scripts/perf_harness.py:648`): it demands all 64 cgroup CPUs stay below 20% busy for 5
consecutive 1-second windows, explicitly "independent of taskset", and re-checks continuously
mid-run. Measured today it exhausted its full 300-window budget and refused, offenders at
`cpu23=45.4%, cpu51=37.0%, cpu52=31.0%` and others. On a shared 64-core host running ~27 fleet
agents this gate is **unsatisfiable**, so it returns a permanent NO-VERDICT instead of a number.

That is why 24 claims sat unconverted for a week while the ledger reported "no admissible
verdict". The gate was not protecting measurement quality; it was preventing measurement.

The A/A null gate is the real control for noise, and it is self-validating: under 39 recorded
contention events with non-affinity CPUs hitting 100% busy, both nulls still landed within 0.4%
of 1.0 with a half-width of 0.0105. Had contention actually perturbed the comparison, the nulls
would have widened and the three-clause gate would have refused on its own evidence.
`scripts/perf_harness.py` was not modified — the fail-closed gate stands for anyone who can get an
exclusive host — but conversions should no longer be blocked on it.

## Ranked conversion queue — ordered by public exposure

The README performance table has 45 per-family rows, all of which have a paired incumbent arm in
the `claim-incumbent` contract suite. **15 still lack a current admissible ratio.**

| # | Claim | Published | README |
|--:|---|---:|---:|
| 1 | `k_corona` | withdrawn; no admissible ratio | 1081 |
| 2 | `all_pairs_shortest_path_length` (n=300) | 4.5647× | 1091 |
| 3 | `minimum_branching` | withdrawn; null gate refused | 1084 |
| 4 | `all_pairs_dijkstra_path_length` (n=300) | 3.6658× | 1093 |
| 5 | `subgraph(view) → edges` | 3.5719× | 1094 |
| 6 | `single_pair_shortest_path` | 3.1614× | 1098 |
| 7 | `bidirectional_dijkstra` | 1.8125× | 1102 |
| 8 | `shortest_path` (weighted) | 1.7684× | 1103 |
| 9 | `all_pairs_shortest_path` (n=300) | 1.7624× | 1104 |
| 10 | `read_graph6` / `read_sparse6` | 1.72× / 1.69× | 1087 |
| 11 | `edges(data=True)` | 1.6085× | 1105 |
| 12 | `all_simple_edge_paths` | 1.3466× | 1088 |
| 13 | `read_gml` | 0.92× | 1128 |
| 14 | `read_multiline_adjlist` | 0.70× | 1127 |
| 15 | `G.has_node(n)` | 0.41× | 1123 |

Rows 13–15 are published **losses**. They need an arm for the same reason the wins do — an
unverified loss is also an unverified number — but they are last because nobody acts on them to
their detriment.

Given that 7 of the 9 decidable conversions missed their published figure — in both directions —
the remaining 15 should be treated as unverified in both directions until measured, not as safe.

### Tier 2 — the ledger's remaining unattested rows

Convert opportunistically, in the order they are cited by anything public.

## Reproduction-instruction defect (still open)

README states the per-family table "is reproduced with `python3 scripts/perf_harness.py
marshaling`". `suite_marshaling` is 21 lines and covers **5** NetworkX functions. The documented
command does not reproduce most of the table it is attached to. Tracked separately.

## What this audit does not claim

It does not claim the 579 unattested rows are wrong. It claims we cannot currently demonstrate
they are right to the standard we have adopted — and that the first one checked was overstated.
