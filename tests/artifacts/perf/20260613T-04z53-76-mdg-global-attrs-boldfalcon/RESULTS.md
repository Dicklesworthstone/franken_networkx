# br-r37-c1-04z53.76 MultiDiGraph Global-Attr Batch

## Target

Fresh current-head profile showed `fnx.MultiDiGraph.add_edges_from(edges, weight=1)`
falling through the Python `_multi_add_edges_from` loop:

- Baseline probe: `0.05899s` FNX median vs `0.01281s` NetworkX median for
  8000 directed multiedges.
- cProfile: `_multi_add_edges_from` / per-edge `add_edge` /
  `get_edge_data` dominated (`2.05s` for 20 constructions).
- Edge digest matched NetworkX:
  `dc97049e2a83c5d61c56f9b519b9b655df07b02e27aca99700f2df121265f5d6`.

## Lever

One lever: extend the existing fresh-graph `PyMultiDiGraph`
`_try_add_attr_edges_from_batch` path to accept optional global attrs, then
dispatch to it only for exact `MultiDiGraph` list/tuple ebunches with non-empty
kwargs.

The batch keeps the existing fallback contract:

- 3-tuples with non-dict third elements are still key tuples and fall back.
- 4-tuples still fall back, preserving partial-error state.
- Non-plain endpoints, display conflicts, unconvertible attrs, and
  `__fnx_incompatible*` attrs fall back without mutation.
- Merge order is NetworkX order: global attrs first, per-edge dict overrides.
- Edge key allocation remains per directed `(u, v)` pair in insertion order.

## Behavior Proof

Harness:
`tests/artifacts/perf/20260613T-04z53-76-mdg-global-attrs-boldfalcon/bench_mdg_global_attrs.py`

Golden cases cover repeated 2-tuples with global attrs, per-edge overrides,
3-tuple key fallback with global attrs, and 4-tuple bad-data prefix state.

- `baseline_golden.json` and `candidate_golden.json` are byte-identical.
- File SHA-256:
  `c06d9f84e1162f92aaf19c8474588c8b0d1565b88c72613ea35f9014b854f8eb`
- Internal payload SHA-256:
  `f5cacf4d182dee4e07884a5a87051702c38a6517a2d40d33d9de555c7689e34c`
- `all_match_networkx: true`
- Benchmark digest unchanged:
  `27c0fe26d35b55c9323955dce9e7a0d8a922f3ee501e06742b58ccc6455c65dc`
- Floating-point/RNG: not applicable; construction-only deterministic edge
  insertion, attr merge, and key-order proof.

## Benchmarks

Isolated overlays:

- Baseline overlay: detached parent commit `04712b536`, freshly built release
  wheel, copied under `/data/tmp/fnx_baseline_overlay_04z53_76`.
- Candidate overlay: current worktree release wheel, copied under
  `/data/tmp/fnx_candidate_overlay_04z53_76`.

Direct loop, 2000 nodes / 8000 directed multiedges, `weight=1`, 60 loops x 9
repeats:

| Build | FNX median | NetworkX median | FNX digest |
| --- | ---: | ---: | --- |
| Baseline | `0.07760117621680061s` | `0.014971732533255514s` | `27c0fe26d35b55c9323955dce9e7a0d8a922f3ee501e06742b58ccc6455c65dc` |
| Candidate | `0.03311823303326188s` | `0.016020634466500875s` | `27c0fe26d35b55c9323955dce9e7a0d8a922f3ee501e06742b58ccc6455c65dc` |

Candidate direct-loop speedup: `2.343x`.

Hyperfine, 30 constructions per process, 10 runs:

- Baseline: `2.4951573925200004s +/- 0.14826413971961214s`
- Candidate: `1.1924867370199999s +/- 0.07634180874132178s`
- Candidate speedup: `2.09x +/- 0.18x`

## Re-profile

`baseline_cprofile.txt`, 20 constructions:

- `_multi_add_edges_from`: `1.920s`
- `add_edge`: `0.890s`
- `get_edge_data`: `0.703s`

`candidate_cprofile.txt`, 20 constructions:

- `_multi_add_edges_from`: `0.530s`
- native `_try_add_attr_edges_from_batch`: `0.530s`
- Python per-edge `add_edge/get_edge_data` no longer appears in the hot path.

Next bottleneck is inside the native batch helper and graph signature /
import overhead, not the Python per-edge fallback.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: passed.
- `rch exec -- maturin build --release --features pyo3/abi3-py310`: passed.
- Focused pytest with candidate in-tree extension:
  `204 passed in 2.05s`.
- `python3 -m py_compile python/franken_networkx/__init__.py ...`: passed.
- `git diff --check`: passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/digraph.rs`: blocked
  by pre-existing formatting drift at lines around 4820, 4854, 4897, 4906,
  4952, and 5904; no touched hunk remains in the rustfmt diff.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: blocked before
  `fnx-python` by pre-existing `fnx-generators` unused return values at
  `crates/fnx-generators/src/lib.rs:538,621,666,6218,6758`.
- `ubs crates/fnx-python/src/digraph.rs python/franken_networkx/__init__.py ...`:
  timed out after 120 seconds after completing the Rust scanner; no UBS pass
  claimed.

## Score

Impact `4` x Confidence `4` / Effort `2` = `8.0`.

Verdict: keep and close `br-r37-c1-04z53.76`.
