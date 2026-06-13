# br-r37-c1-04z53.77 Results

## Target

Profile-backed hotspot: `fnx.MultiGraph.add_edges_from(8000 2-tuples, weight=1)`
on exact fresh `MultiGraph`.

Parent profile after `e0092fde4`:

- FNX median: `0.051964106160012305s`
- NetworkX median: `0.011895062710100318s`
- Digest: `205b78af5a8f5283cdedc1d42a46b2d0c8fd206a4844d81f35af24c30bc6619e`
- cProfile: Python fallback dominated by `_multi_add_edges_from`, `add_edge`,
  and `get_edge_data`.

## Lever

Extend the existing native fresh-multigraph attributed-edge batch helper to accept
non-empty global `**attr` for exact `MultiGraph` as well as `MultiDiGraph`.

The native path is still gated to the same narrow safe surface:

- exact class is `MultiGraph` or `MultiDiGraph`
- graph is fresh
- `ebunch_to_add` is a list/tuple with at least 8 entries
- nodes are plain compatible node keys
- edge tuples are `(u, v)` or `(u, v, dict)`
- explicit key 3-tuples and 4-tuples fall back to the Python path
- attr values that cannot be mirrored or trip `__fnx_incompatible*` fall back

Global attrs are merged first and per-edge attrs override, matching NetworkX.
Mirror dicts are fresh copies; caller dicts are not aliased.

## Behavior Proof

- Ordering preserved: yes. Native helper iterates the input `ebunch_to_add` in
  order and assigns the same sequential per-pair keys as the fresh per-edge path.
- Tie-breaking preserved: yes. No algorithmic tie-breaking is touched.
- Floating-point behavior: N/A. This path stores Python attr objects and does no
  numeric computation.
- RNG behavior: N/A.
- Error and partial-prefix behavior: preserved by returning `false` before any
  mutation for explicit-key, 4-tuple, incompatible attr, non-plain-node, or
  display-conflict surfaces so the existing Python loop owns those contracts.
- Golden output: unchanged and NetworkX-matching.

Golden artifact SHA:

```text
980faf66996fcd7a84dab74796cb25fb74e54b64d3375dabb06a1e78af5b534a  baseline_golden.json
980faf66996fcd7a84dab74796cb25fb74e54b64d3375dabb06a1e78af5b534a  candidate_golden.json
```

Embedded semantic SHA in both golden files:

```text
b1149eb6755c3ec46023dfbd16cbc3822394c6238370a3d7b0a97b8a0ed04ea8
```

Construction digest for benchmark graph:

```text
c34547d2882e92ecff188201d9be2c41c5d7d2e0caeac70f23f07bc490f204d8
```

Baseline/candidate FNX and NetworkX benchmark digests all matched.

## Benchmark

Direct rch benchmark, 60 loops x 9 repeats:

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| FNX median seconds | `0.07683763285021997` | `0.026119409083185018` | `2.94x faster` |
| FNX best seconds | `0.06560782341669741` | `0.02293365424993681` | `2.86x faster` |
| NetworkX median seconds | `0.014157857033327066` | `0.014094764950035218` | comparator stable |
| FNX vs NetworkX ratio | `0.18425680891191765` | `0.5396280178141187` | gap reduced |

Hyperfine, `--warmup 2 --runs 10`, 30 constructions per command:

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Mean seconds | `2.15652649622` | `1.58819863592` | `1.36x faster` |
| Median seconds | `2.17106059062` | `1.54468178162` | `1.41x faster` |
| Stddev seconds | `0.13711491782094246` | `0.216711692087753` | recorded |

Score: `2.94 * 4 / 1 = 11.77`, keep.

## Profile Shift

Baseline cProfile, 20 constructions:

- `3,600,161` calls in `2.244s`
- `_multi_add_edges_from`: `2.244s` cumulative
- `add_edge`: `1.052s` cumulative over `160,000` calls
- native `MultiGraph.add_edge`: `0.929s`
- `get_edge_data`: `0.830s`

Candidate cProfile, 20 constructions:

- `141` calls in `0.518s`
- `_multi_add_edges_from`: `0.517s` cumulative
- `_try_add_attr_edges_from_batch`: `0.517s` over `20` calls
- Python per-edge `add_edge` and `get_edge_data` frames are gone.

## Validation

- `PYTHONPATH=/data/tmp/fnx_candidate_clean_overlay_04z53_77 python3 -m pytest tests/python/test_attribute_access_parity.py tests/python/test_adj_row_key_parity.py tests/python/test_ctor_str_and_third_element_parity.py tests/python/test_mutation_sequence_metamorphic_parity.py -q --tb=short`
  passed: `204 passed`.
- `python3 -m py_compile python/franken_networkx/__init__.py .../bench_mg_global_attrs.py`
  passed.
- `rch exec -- cargo check -p fnx-python --lib` passed.
- `git diff --check` passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs` blocked on
  pre-existing formatting drift in `fnx-python` files outside this lever.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` blocked on
  pre-existing `fnx-generators` unused `extend_*_unrecorded` return warnings.
- `timeout 120 ubs crates/fnx-python/src/lib.rs python/franken_networkx/__init__.py .../bench_mg_global_attrs.py`
  timed out after finishing Rust scan and while scanning Python.

## Artifacts

```text
980faf66996fcd7a84dab74796cb25fb74e54b64d3375dabb06a1e78af5b534a  baseline_golden.json
980faf66996fcd7a84dab74796cb25fb74e54b64d3375dabb06a1e78af5b534a  candidate_golden.json
9ede590a1bfcb516431741362505a3d6781467ba6ecee75ddbe7dd76a196ae08  baseline_bench.json
6271c6562131ccb1b3d3044097567943603854c5132ba7217598e340533f3a0c  candidate_bench.json
2aebfea5aa371255b5c2bf0d0a740d9809c35b77509c91236533485981eb43ec  hyperfine.json
aeacf0a2acfaec83390a765868d1e046a712211b0e5dca0e5afe6a27287efcef  baseline_cprofile.txt
1f6b9b61bc48a57c187494d1c40c4040bf298ff4f5602f7186aae938c55b2a54  candidate_cprofile.txt
```
