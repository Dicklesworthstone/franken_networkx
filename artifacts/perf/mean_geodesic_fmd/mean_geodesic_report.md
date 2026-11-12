# Giant-component mean geodesic: FrankenNetworkX vs NetworkX 3.6.1

Target class: **MISSING CAPABILITY**. This is the whole job a network analyst runs to report mean geodesic separation on the giant connected component, including parsing, cleanup, component discovery, component materialisation, and the exact all-sources distance calculation.

## Why the incumbent target is unavailable

Live NetworkX 3.6.1 exposes `average_shortest_path_length(G, weight=None, method=None, *, backend=None, **backend_kwargs)`. With automatic backend dispatch disabled, that core signature has **no `n_jobs`, `threads`, or `workers` control**. Its all-sources Python traversal therefore has no many-core arm to select. This is an absent target, not a slower setting: there can be no honest `nx@N` timing row.

FNX has a Rayon source-parallel traversal. The artifact does not infer that capability from a requested pool size: it counts the process threads whose Linux scheduler CPU counters actually advance during the distance stage. A structural verdict requires exactly one active NetworkX thread and more than one active FNX thread in the admitted head-to-head.

## Measurement provenance

| field | value |
| --- | --- |
| study started | `2026-10-25T04:22:39+0000` |
| study finished | `2026-10-25T04:29:57+0000` |
| host | `fixmydocuments` |
| CPU | `AMD Ryzen 7 5800X 8-Core Processor` |
| cores | 8 physical / 16 SMT; affinity 14 |
| live NetworkX | `3.6.1` at `/data/projects/franken_networkx/venv/lib/python3.14/site-packages/networkx/__init__.py` |
| NetworkX auto-backend env | `<unset>` |
| in-process fnx ELF | `/data/projects/franken_networkx/python/franken_networkx/_fnx.abi3.so` |
| **in-process fnx ELF SHA-256** | `52c586d7be6f38b4321270d86f4c597af1b7d843ab5e6b0e3a5bb1f603a77def` |
| build worker | `ts1` |
| cargo profile | `release` |
| rch `--base` | `c58ed6e164149851d31912badb8adb3df93cf3e0` |
| rch `--clean-overlay` | `True` |
| requested target | `/data/tmp/cargo-target` |
| in-process observed target | `/data/tmp/rch/franken_networkx/.rch-target-ts1-pool` |
| emitted timing rows | 126 |

- `facebook_combined` exact input: `/data/projects/franken_networkx/graphs/facebook_combined.txt.gz`, 218576 bytes, SHA-256 `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`.

Every CSV row repeats the job, exact input identity, host, actual CPU-active threads, live NetworkX version, in-process ELF hash, build worker/profile, `rch --base`, `--clean-overlay`, requested and in-process observed target paths, both admission verdicts, and the continuous exclusivity verdict.

## Fail-closed attempts

| graph | engine | requested threads | no-verdict reasons |
| --- | --- | --- | --- |
| `facebook_combined` | nx | 8 | host-wide benchmark exclusivity failed at pre_setup after 300 windows; required 5 consecutive clear windows: cpu2=100.0%, cpu10=100.0%; status=NO-VERDICT; no completed replicates; host-wide pre_setup admission not clear; host-wide pre_measurement admission not clear; continuous measurement exclusivity not clear; continuous measurement accounting has no windows |
| `facebook_combined` | fnx | 8 | host-wide benchmark exclusivity failed at pre_setup after 300 windows; required 5 consecutive clear windows: cpu2=100.0%, cpu10=100.0%; status=NO-VERDICT; no completed replicates; host-wide pre_setup admission not clear; host-wide pre_measurement admission not clear; continuous measurement exclusivity not clear; continuous measurement accounting has no windows |

These attempts contribute no chooser fact. A worker abort clears all partial replicates, so contaminated numbers cannot leak into a ratio.

## The whole job

```text
read_edgelist -> remove_self_loops -> connected_components
  -> giant_component.subgraph(...).copy()
  -> average_shortest_path_length (exact, every source)
```

The graph read and giant-component copy remain inside the timed job. Removing either would turn a user workflow into a kernel benchmark.

## Exact cross-engine parity

No completed head-to-head pair is available; parity is unproven.

Any divergence vetoes the speed claim. The exact producing input is attached to each divergent field rather than summarized away.

## CHOOSER STATEMENT

- **Choose NetworkX 3.6.1 for now.** No row simultaneously clears exact parity, both A/A controls, all three median-gate clauses, host-wide admission and continuous accounting, strict RCH provenance with one observed physical target for both arms, and an observed one-vs-many thread split.
- Revisit only after one clean invocation produces that complete evidence chain; a requested Rayon size or a self-speedup alone is not a campaign win.

