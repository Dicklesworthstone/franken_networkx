# br-r37-c1-04z53.9110 reverse view edges baseline/profile

Scope: evidence-only capture for `list(DG.reverse(copy=False).edges())`.
No source, test, or Beads files were edited.

## Commands

Golden:

```bash
env PYTHONPATH=/data/projects/franken_networkx/python \
  .venv/bin/python \
  tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py \
  golden \
  --output tests/artifacts/perf/20260615T-reverse-view-coppercliff/baseline_golden.json
```

Direct in-process timing, graph built once per impl:

```bash
env PYTHONPATH=/data/projects/franken_networkx/python \
  .venv/bin/python \
  tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py \
  bench --impl fnx --repeats 31 \
  --output tests/artifacts/perf/20260615T-reverse-view-coppercliff/baseline_direct_fnx.json

env PYTHONPATH=/data/projects/franken_networkx/python \
  .venv/bin/python \
  tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py \
  bench --impl nx --repeats 31 \
  --output tests/artifacts/perf/20260615T-reverse-view-coppercliff/baseline_direct_nx.json
```

Profile:

```bash
env PYTHONPATH=/data/projects/franken_networkx/python \
  .venv/bin/python \
  tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py \
  profile --impl fnx --loops 100 --limit 35 \
  --output tests/artifacts/perf/20260615T-reverse-view-coppercliff/baseline_profile_fnx.txt
```

RCH-prefixed hyperfine:

```bash
rch exec -- hyperfine --warmup 3 --runs 15 \
  --export-json tests/artifacts/perf/20260615T-reverse-view-coppercliff/baseline_hyperfine_loop100.json \
  'env PYTHONPATH=/data/projects/franken_networkx/python /data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py once --impl fnx --loops 100' \
  'env PYTHONPATH=/data/projects/franken_networkx/python /data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260615T-reverse-view-coppercliff/reverse_view_edges_harness.py once --impl nx --loops 100'
```

`rch` warned that this was a non-compilation command, then ran the
hyperfine command successfully.

## Case

Harness parameters:

- `nodes=1200`
- `k=10`
- `p=0.2`
- `seed=5`
- `style=digraph_ctor`
- `edge_count=12000`

This reproduces the same target surface and edge count scale, but does
not reproduce the bead's historical expected SHA. The artifact records
both hashes instead of forcing the mismatch.

## Golden

- FNX SHA: `042baf3e7f3df78ebd2f0449150004d3f1db72722c268721b598f173efc5d73b`
- NetworkX SHA: `042baf3e7f3df78ebd2f0449150004d3f1db72722c268721b598f173efc5d73b`
- FNX matches NetworkX: yes
- Historical bead expected SHA: `6c02e12d4919dc3896f61bb46132765c58d07395023846106aad288d1c918feb`
- Matches historical expected SHA: no

## Timing

Direct materialization-only timing, graph built once:

| Impl | Median | Mean | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| FNX | `0.0058617530s` | `0.0070291828s` | `0.0050252880s` | `0.0206442820s` |
| NetworkX | `0.0009103040s` | `0.0014936461s` | `0.0007201940s` | `0.0162694850s` |

Median ratio: FNX is `6.44x` slower on this harness.

RCH-prefixed hyperfine, `once --loops 100`:

| Impl | Mean command time | Median command time |
| --- | ---: | ---: |
| FNX | `0.9477103222s` | `0.9334253196s` |
| NetworkX | `0.3911884073s` | `0.3830361696s` |

Hyperfine summary: NetworkX ran `2.42 +/- 0.25x` faster. This process
benchmark includes one graph build plus 100 materializations, so the
direct in-process timing above is the cleaner materialization number.

## cProfile Hotspots

FNX profile over 100 materializations:

- `__init__.py:34637(_edges)`: `2.181s` cumulative, `0.628s` tottime
- `__init__.py:1138(<genexpr>)`: `0.850s` cumulative
- `__init__.py:1252(AtlasView.__getitem__)`: `0.596s` cumulative
- `__init__.py:1210(AtlasView._keydict)`: `0.300s` cumulative
- `__init__.py:36609(_private_pred_mapping)`: `0.177s` cumulative

## Next Primitive Candidate

Target [python/franken_networkx/__init__.py:34637](/data/projects/franken_networkx/python/franken_networkx/__init__.py:34637):
`_ReverseDirectedViewBase._edges` materializes by repeatedly walking
`self._graph.pred[source].items()`, which descends through Python mapping
wrappers and per-neighbor `AtlasView` lookups.

The next pass should design a bulk reverse-edge materialization primitive
for plain `DiGraph` reverse views, preserving exact node-major reverse
edge order and the existing `data`, `default`, `nbunch`, and multigraph
semantics. The profile points to bypassing the per-edge
`AtlasView.__getitem__` / `_keydict` wrapper stack, not to graph
construction.

## Artifacts

- `reverse_view_edges_harness.py`
- `baseline_golden.json`
- `baseline_direct_fnx.json`
- `baseline_direct_nx.json`
- `baseline_profile_fnx.txt`
- `baseline_hyperfine_loop100.json`
- `RESULTS.md`
- `__pycache__/reverse_view_edges_harness.cpython-313.pyc` (created by `py_compile`; left in place per no-delete rule)
