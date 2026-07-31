# Claim coverage audit — how much of our claimed ground rests on an incumbent comparison

**Date:** 2026-07-30 · **Auditor:** BlackThrush (cc) · **HEAD:** `71ff895de`
**Trigger:** fleet policy — a perf KEEP requires a vs-incumbent ratio. frankenfs audited itself
and found 67 of 186 KEEP claims carried none. This is the same audit run here.
**Scope:** inventory only. No claim is deleted or weakened by this document.

## Headline

Of **591** KEEP claim rows across the three active ledgers, **12 carry a vs-incumbent ratio
measured with NetworkX live in the same invocation** and **579 do not** — 2.0% attested coverage.

Reproduce with `python3 scripts/perf_ledger_preflight.py --audit`.

## What "carries a ratio" means here

The repo's own gate (`scripts/perf_ledger_preflight.py`, adopted 2026-07-25) defines a campaign
claim as carrying all of:

```
comparison_class=INCUMBENT
incumbent=networkx
incumbent_same_invocation=true
incumbent_ratio=<numeric>
campaign_output=true
```

That machine-readable attestation is the only thing that is *checkable*, so it is the number
reported above. Prose that says "41.6x vs nx" is not the same evidence: it does not record
whether NetworkX ran in that invocation or whether the figure came from a different session,
machine, or build.

## Breakdown of the 591

| Class | Rows | Meaning |
|---|---:|---|
| contract `INCUMBENT` | 12 | attested same-invocation incumbent ratio |
| declared `SELF-SPEEDUP` | 2 | honest maintenance, correctly not a campaign claim |
| ratio, prose asserts vs-nx, no attestation | ~203 | plausibly convertible by re-measurement |
| ratio, no identifiable incumbent arm (causal/mechanism) | ~365 | self-speedup shaped |
| no numeric ratio at all | 9 | note/milestone KEEPs |

Also: **39 of 591** carry the in-process loaded-ELF SHA-256; **552 do not**.

The last two prose buckets are a regex split over free text and are an estimate, ±. The 12 / 2 /
9 counts and the 39 ELF count come from the gate's own classifier and are exact. Most of the 591
predate the 2026-07-25 contract, so the 2.0% is a measure of *attestation*, not proof that 579
levers were never compared to NetworkX.

## Ranked conversion queue — ordered by public exposure, not by ledger position

An unsupported claim a user might act on is worse than one buried in a ledger. So the queue is
ranked by what `README.md` publishes.

The README performance table has 45 per-family rows: 44 numeric claims and one
explicit no-ratio row after the contaminated `k_corona` number was withdrawn.
It also has 5 whole-job pipeline rows. Cross-referencing each family row against
a paired `(label, nx_arm, fnx_arm)` job in the contract harness across **all 33
suites** (the harness exposes **35 distinct NetworkX functions** with a paired arm):

- **26 of 45** README family rows have a paired incumbent arm in the contract harness.
- **19 of 45** do not.
- **24 of 45** still lack a current admissible ratio. The
  `erdos_renyi_graph` and `k_corona` arms reached no timed verdict because host
  exclusivity rejected their runnable placements. The `k_crust` and
  `single_source_shortest_path_length` and
  `kosaraju_strongly_connected_components` arms reached no timed verdict
  because RCH 1.0.52 gives every required clean-overlay execution a
  UUID-salted remote root, so its otherwise pooled Cargo target cannot be
  reused without minting another cold target directory.

### Tier 1 — published in the README, no current admissible contract ratio

Rows 1-5 now have permanent arms but remain in this queue until they reach an
admissible verdict. Rows 6-24 still have no permanent arm.

| # | Claim | Published | README |
|--:|---|---:|---:|
| 1 | `erdos_renyi_graph` (n=1500) | 14.1755× | 1080 |
| 2 | `k_corona` | withdrawn; no admissible ratio | 1081 |
| 3 | `k_crust` | 5.8664× | 1082 |
| 4 | `single_source_shortest_path_length` | 5.5005× | 1090 |
| 5 | `kosaraju_strongly_connected_components` | 4.6519× | 1083 |
| 6 | `all_pairs_shortest_path_length` (n=300) | 4.5647× | 1091 |
| 7 | `minimum_branching` | 3.9768× | 1084 |
| 8 | `all_pairs_dijkstra_path_length` (n=300) | 3.6658× | 1093 |
| 9 | `subgraph(view) → edges` | 3.5719× | 1094 |
| 10 | `single_pair_shortest_path` | 3.1614× | 1098 |
| 11 | `pagerank` | 2.6361× | 1099 |
| 12 | `partition_spanning_tree` | 2.4612× | 1085 |
| 13 | `to_scipy_sparse_array` | 2.4073× | 1100 |
| 14 | `label_propagation_communities` | 2.1485× | 1078 |
| 15 | `dfs_successors` | 2.1456× | 1086 |
| 16 | `bidirectional_dijkstra` | 1.8125× | 1102 |
| 17 | `shortest_path` (weighted) | 1.7684× | 1103 |
| 18 | `all_pairs_shortest_path` (n=300) | 1.7624× | 1104 |
| 19 | `read_graph6` / `read_sparse6` | 1.72× / 1.69× | 1087 |
| 20 | `edges(data=True)` | 1.6085× | 1105 |
| 21 | `all_simple_edge_paths` | 1.3466× | 1088 |
| 22 | `read_gml` | 0.92× | 1128 |
| 23 | `read_multiline_adjlist` | 0.70× | 1127 |
| 24 | `G.has_node(n)` | 0.41× | 1123 |

Rows 22–24 are published **losses**. They need an arm for the same reason the wins do — an
unverified loss is also an unverified number — but they are last in the queue because nobody acts
on them to their detriment.

### Tier 2 — the ledger's ~568 unattested rows

Convert opportunistically, in the order they are cited by anything public. A ledger row nobody
reads is the cheapest place for an unsupported number to sit.

## Reproduction-instruction defect found during the audit

README states the per-family table "is reproduced with `python3 scripts/perf_harness.py
marshaling`". `suite_marshaling` is 21 lines and covers **5** NetworkX functions (`bfs_tree`,
`dfs_tree`, `node_link_data`, `single_source_shortest_path`, `to_dict_of_lists`). The documented
command therefore does not reproduce most of the table it is attached to. Tracked separately.

## Explicitly: nothing here is unconvertible

The fleet policy asks that a claim which *cannot* be converted — because no incumbent arm exists
for that surface — be named as such, since that is a different problem from a claim nobody has
gotten around to measuring.

**No claim in this repo is in that category.** Every function in the Tier 1 queue exists in
NetworkX 3.6.1; being a drop-in replacement is the whole premise. Adding an arm is mechanical: a
`(label, lambda: nx.f(g), lambda: fnx.f(g))` triple in an existing suite. The accessor rows
(`edges(data=True)`, `G.has_node`, `subgraph(view) → edges`) need a bound-method arm, which the
harness already supports (`getattr(nx_graph, name)`, `perf_harness.py:2580`).

So the honest characterisation is **"measured but not attested; 19 public
cases are not reproducible by the contract harness, and five more now have
permanent arms but no admissible verdict"** — not "unmeasurable". That is a
better position than the raw 2.0% suggests, and a worse one than the README
implies.

## What this audit does not claim

It does not claim the 579 unattested rows are wrong. It claims we cannot
currently demonstrate they are right to the standard we have adopted, and
that 20 numbers a user reads in the README have no arm in the harness it
points them at; four more now have arms but no admissible timed verdict.
