# br-r37-c1-7x2z3 generate_adjlist native line builder

## Target

Profile-backed residual after the LPA closeout: exact simple `Graph`
`generate_adjlist` on prebuilt `barabasi_albert_graph(1800, 4, seed=101)`
was still slower than NetworkX because the Python wrapper called
`_native_adjacency_keys`, materialized `(node, [neighbors])` Python rows, then
rebuilt every output line in Python.

## One lever

Add `_native_generate_adjlist_lines(delimiter)` on exact simple `PyGraph` and
route `generate_adjlist` through it only when:

- `type(G) is franken_networkx.Graph`;
- `delimiter` is an exact Python `str`;
- there are no adjacency Python display keys (`_native_has_adj_py_keys()` is
  false).

Directed graphs, multigraphs, subclasses, non-string delimiters, and graphs
with adjacency display keys stay on the previous path.

## Baseline and result

Direct benchmark, 100 repeats after 10 warmups:

| Backend | p50 before | p50 after | mean before | mean after |
| --- | ---: | ---: | ---: | ---: |
| FNX | 3.289763 ms | 1.632929 ms | 3.274254 ms | 1.779027 ms |
| NetworkX control | 2.188913 ms | 1.441892 ms | 2.479795 ms | 1.900271 ms |

FNX direct self-speedup: `2.01x` p50, `1.84x` mean.

RCH-wrapped hyperfine, 12 runs, 40 calls/process:

| Command | mean before | mean after | delta |
| --- | ---: | ---: | ---: |
| FNX | 0.514142 s | 0.378705 s | 1.36x faster |
| NetworkX control | 0.488586 s | 0.361566 s | control/import envelope drift |

cProfile over 240 FNX calls dropped from `1.516s` / `1,298,882` calls to
`0.460s` / `435,602` calls. The old `_native_adjacency_keys` row snapshot
(`0.349s`) disappeared; the replacement native line builder accounts for
`0.395s` of the after profile.

## Isomorphism proof

Golden/proof cases cover the BA target graph, comma delimiter, self-loop,
string labels, directed fallback, and multigraph fallback.

- Baseline proof file SHA: `a8771c66ea38dde01558b9d394e2ce4bd9e75e069ca486a7ec2ceef50b90fd23`
- After proof file SHA: `a8771c66ea38dde01558b9d394e2ce4bd9e75e069ca486a7ec2ceef50b90fd23`
- Embedded proof SHA: `36ef12df3f78ee4a5c1cd055753ce8dff7bca99393f35861903e39c982b21fc1`
- FNX golden file SHA unchanged:
  `07f4bcada104793ee6055fe20d0438c7d3aaab9d3eecce73b91fe10964cb4fe9`
- Target text SHA unchanged and matches the NetworkX control:
  `37b95d4cb8f336275a817fc6752b56a5585cb884d60bdc37b160df1d87c4fd16`

Ordering is still graph insertion order plus neighbor insertion order with the
same undirected "already seen node" suppression. Tie-breaking is not used.
There is no floating-point surface. RNG is limited to deterministic fixture
construction with seed `101`.

## Gates

- `py_compile` for `python/franken_networkx/readwrite/__init__.py` and the
  harness: passed.
- `pytest tests/python/test_io_variants.py tests/python/test_io.py tests/python/test_read_adjlist_native_parity.py -q`:
  `90 passed in 0.68s`.
- `git diff --check`: passed.
- `ubs` on touched code and harness: exit `0`, no critical findings; broad
  pre-existing warnings remained in large files.
- RCH `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`:
  passed on `vmi1227854` with pre-existing `fnx-generators` and
  `fnx-algorithms` warnings.
- `cargo fmt --check --manifest-path crates/fnx-python/Cargo.toml` remains
  blocked by pre-existing formatting drift in untouched Rust code; the new
  block was not reported.

## Verdict

PRODUCTIVE / kept. Score `5.5` (`Impact 3.0 * Confidence 3.7 / Effort 2.0`).

Next target after closeout: reprofile current `main`; remaining adjlist cost is
native string conversion plus Python generator iteration, so do not repeat row
snapshot tuning. Attack a deeper output-streaming primitive only with an exact
proof for file writing, comments/header behavior, delimiter semantics, and
display-object ordering.
