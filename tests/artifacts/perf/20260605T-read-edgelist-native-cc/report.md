# perf: read_edgelist / read_weighted_edgelist native single-pass parser (br-r37-c1-7nen2)

## Problem

Default-kwargs `read_edgelist` delegated to nx parse + per-edge
`_from_nx_graph` rebuild: no-data files 5.39x, weighted 2.81x vs nx
(sweep, n=1500/E=5217, warm min-of-9). Same shape as read_adjlist
before br-r37-c1-770mm.

## Lever (one)

`_fnx.read_edgelist_simple(path, mode)` — single-pass parse straight
into the final PyGraph (canon-cached tokens, bulk
extend_nodes_unrecorded + extend_edges_with_attrs_unrecorded — the
pr8q6 attributed bulk API). Modes gated by the Python wrappers:
- data_true: every line EXACTLY 2 tokens (extras need literal_eval +
  an nx-specific TypeError -> bail);
- data_false: first 2 tokens, extras ignored;
- weight_float: 3rd token parsed as f64 (Rust from_str == CPython
  float() for sign/decimal/exp/inf/infinity/nan spellings, both
  correctly-rounded; underscore separators are Python-only -> bail);
  2 tokens -> edge with {} (nx leaves it empty); >3 -> bail (nx
  IndexError). Duplicate edges overwrite weight (nx datadict.update).

Line semantics mirror nx.parse_edgelist exactly: comment strip, ws
tokenization, `len(s) < 2 -> continue` (blank / ws-only / one-token
lines silently SKIPPED — probed, unlike parse_adjlist which raises).

Also fixed in passing: fnx read_weighted_edgelist passed
data=[("weight", float)] (list) where nx uses a tuple — the container
repr leaks into the IndexError message on length-mismatched lines, a
pre-existing error-message divergence caught by this proof.

## Parity proof (parity_proof.py)

105/105 cases, 0 failures: 30 nx-written no-data corpora (unicode/str
labels, both data=True/False reads), 20 weighted corpora, 9 + 10
hand-crafted files (blank/one-token lines, comments, tabs, CRLF, dup
edges incl. weight overwrite, self-loops, no trailing newline, extras
with data=False, exp/inf/nan/-Infinity/NAN/-0.0/1e309-overflow floats,
underscore delegation), weighted error parity (type AND message),
dict-column files (delegate), non-default kwargs (delegate), missing
file, post-read mutability + dijkstra exactness.

GOLDEN_CORPUS_SHA256: adf92dab3a1111cff958e01e8ca54a039ffedc604e79adec832d3cbcccddfee9
(unchanged across the clippy collapse-if-let cleanup rebuild)

## Bench (interleaved warm min-of-12, n=1500/E=5217)

- read_edgelist(no-data file):  39.8ms -> 5.2ms; 5.39x -> 0.84x (FASTER than nx)
- read_edgelist(data=False):            -> 4.5ms; -> 0.77x
- read_weighted_edgelist:       32.6ms -> 6.2ms; 2.81x -> 0.62x (1.6x FASTER)

## Validation

- tests/python/test_read_edgelist_native_parity.py: 25 passed
  (+ read_adjlist sibling suite 18 passed)
- full tests/python suite: 21359 passed; 6 failures identical to HEAD
  (pre-existing: multigraph constructor/fuzz + coverage matrix)
- clippy: no new warnings after collapse-if-let fix
- built in isolated worktree at HEAD b5f1b3bbc + only these files;
  private CARGO_TARGET_DIR=/data/tmp/cargo-target-cc
