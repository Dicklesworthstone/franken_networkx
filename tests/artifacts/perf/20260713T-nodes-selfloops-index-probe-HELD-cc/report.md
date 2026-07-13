# nodes_with_selfloops index self-loop probe — MEASURED 5.1x, HELD for peer reservation (cc, 2026-07-13)

A ready, measured perf lever that is **not landed this turn** — blocked by an ACTIVE agent-mail file
reservation on `crates/fnx-algorithms/src/lib.rs` held by peer **MagentaTrout** (codex/gpt-5, doing
concurrent one-lever perf work; their uncommitted `is_isolate` WIP is in the shared checkout). I
respected the pre-commit reservation guard rather than override it. The change + A/B are preserved as
patches and will land when the file frees.

## The lever (br-r37-c1-selfloopidx)

`fnx_algorithms::nodes_with_selfloops` (lib.rs ~44289) probed each node's self-loop with
`has_edge(node, node)` — which resolves BOTH `&str` endpoints to indices via `edge_pair_key` (two
String-hash lookups per node) before the `(min,max)` `contains_key`. Switch to
`has_edge_by_indices(i, i)` (a direct integer `canon_pair` + `contains_key`, NO String resolution),
iterating by index — the undirected twin of the shipped directed `nodes_with_selfloops_rust`
selfloopdir fast path. Byte-identical (`has_edge_by_indices(i,i)` == `has_edge(nodes_ordered()[i],
same)`, same emission order). LIVE: feeds `number_of_selfloops` / `selfloop_edges` /
`nodes_with_selfloops` (many internal callers, e.g. the `is_eulerian` self-loop guard).

## Measured (GIL-free fnx-classes A/B `nodes_selfloop_idx_ab`, ring-of-chords n=40000 deg=10, no self-loops, 61 rounds)

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `HASEDGEIDX_vs_hasedge` | **5.15x** | 61/61 | [3.48, 7.95] |
| `NULL_new_vs_new`       | 1.37x | 60/61 | [1.06, 2.10] |

Candidate p5 (3.48) > null p95 (2.10) — clears the strict gate. The null is wide because the sub-ms
scan is timing-noisy, but the change is STRICTLY less work (integer lookup vs String resolution), so
zero regression risk regardless of the null width. Parity asserted (same self-loop count).

## Why HELD (coordination)

The pre-commit guard (`mcp-agent-mail`) blocked the commit:
`crates/fnx-algorithms/src/lib.rs conflicts with reservation held by MagentaTrout`. MagentaTrout is a
live, active peer (last active minutes ago). Even though my hunk (`nodes_with_selfloops`, a different
function than their `is_isolate` WIP) is provably non-conflicting and I staged it via `git hash-object`
to exclude their WIP, overriding an active peer's reservation is bad etiquette. Held per
[[parallel_work_collision_detection]] / [[active_agents]].

## To land (patches saved in this session's scratchpad)

`mine_algos.patch` (the nodes_with_selfloops kernel change) + `mine_fnxclasses_test.patch` (the A/B
test). When MagentaTrout releases `crates/fnx-algorithms/src/lib.rs`: re-apply both, re-run the A/B
to reconfirm, then commit (only my hunk via hash-object if their WIP is still present) + push.
