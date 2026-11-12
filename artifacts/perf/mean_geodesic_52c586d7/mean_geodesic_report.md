# Giant-component mean geodesic: FrankenNetworkX vs NetworkX 3.6.1

Target class: **MISSING CAPABILITY**. This is the whole job a network analyst runs to report mean geodesic separation on the giant connected component, including parsing, cleanup, component discovery, component materialisation, and the exact all-sources distance calculation.

## Why the incumbent target is unavailable

Live NetworkX 3.6.1 exposes `average_shortest_path_length(G, weight=None, method=None, *, backend=None, **backend_kwargs)`. With automatic backend dispatch disabled, that core signature has **no `n_jobs`, `threads`, or `workers` control**. Its all-sources Python traversal therefore has no many-core arm to select. This is an absent target, not a slower setting: there can be no honest `nx@N` timing row.

FNX has a Rayon source-parallel traversal. The artifact does not infer that capability from a requested pool size: it counts the process threads whose Linux scheduler CPU counters actually advance during the distance stage. A structural verdict requires exactly one active NetworkX thread and more than one active FNX thread in the admitted head-to-head.

## Measurement provenance

| field | value |
| --- | --- |
| study started | `2026-10-25T04:30:51+0000` |
| study finished | `2026-10-25T04:41:13+0000` |
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
| emitted timing rows | 378 |

- `facebook_combined` exact input: `/data/projects/franken_networkx/graphs/facebook_combined.txt.gz`, 218576 bytes, SHA-256 `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`.

Every CSV row repeats the job, exact input identity, host, actual CPU-active threads, live NetworkX version, in-process ELF hash, build worker/profile, `rch --base`, `--clean-overlay`, requested and in-process observed target paths, both admission verdicts, and the continuous exclusivity verdict.

## The whole job

```text
read_edgelist -> remove_self_loops -> connected_components
  -> giant_component.subgraph(...).copy()
  -> average_shortest_path_length (exact, every source)
```

The graph read and giant-component copy remain inside the timed job. Removing either would turn a user workflow into a kernel benchmark.

## `facebook_combined` -- 4039 input nodes, 4039 giant-component nodes

| stage | nx wall (s) | nx actual threads | fnx@8 wall (s) | fnx actual threads | speedup |
| --- | --- | --- | --- | --- | --- |
| read_edgelist | 0.124 | 1.0 | 0.010 | 9.0 | 12.01x |
| remove_self_loops | 0.000 | 1.0 | 0.000 | 1.0 | 2.83x |
| connected_components | 0.006 | 1.0 | 0.000 | 1.0 | 13.52x |
| giant_component_copy | 0.191 | 1.0 | 0.010 | 1.0 | 19.37x |
| average_shortest_path_length | 18.346 | 1.0 | 0.002 | 9.0 | 7801.99x |
| **TOTAL** | **18.662** | 1.0 | **0.023** | 9.0 | **808.50x** |

### Corrected three-clause median gate

| clause | observation | pass |
| --- | --- | --- |
| effect | median nx/fnx **808.505x**, 95% bootstrap CI [761.957, 859.416] | yes |
| resolution | deviation 807.5047 > 2 x larger null half-width 0.2067 | yes |
| null medians | worst bias 0.0634 <= 0.0200 | **NO** |
| **verdict** | **UNDECIDABLE** | |

- NetworkX A/A null median 1.0208, CI [0.9655, 1.0709], half-width 0.0527.
- FNX A/A null median 1.0634, CI [0.9472, 1.1539], half-width 0.1034.

## Exact cross-engine parity

- `facebook_combined`: **AGREE** on all ten digest fields in all 21 paired replicates, including exact mean geodesic `3.6925068496963913`; input SHA-256 `125e84db872eeba443d270c70315c256b0af43a502fcfe51f50621166ad035d7`.

Any divergence vetoes the speed claim. The exact producing input is attached to each divergent field rather than summarized away.

## FNX thread sweep -- `facebook_combined`

| requested | actual active | distance wall (s) | scaling vs 1 |
| --- | --- | --- | --- |
| 1 | 1.0 | 0.007 | 1.00x |
| 8 | 9.0 | 0.002 | 2.88x |

The requested column is configuration; the active column is the observed capability evidence.

## CHOOSER STATEMENT

- **Choose NetworkX 3.6.1 for now.** No row simultaneously clears exact parity, both A/A controls, all three median-gate clauses, host-wide admission and continuous accounting, strict RCH provenance with one observed physical target for both arms, and an observed one-vs-many thread split.
- Revisit only after one clean invocation produces that complete evidence chain; a requested Rayon size or a self-speedup alone is not a campaign win.

