# perf: read_adjlist native single-pass parser (br-r37-c1-770mm)

## Problem

`fnx.read_adjlist` (default kwargs) delegated parsing to `nx.read_adjlist`
and then rebuilt the result with `_from_nx_graph` — a per-edge
`add_edge` walk that was 78% of the call (cProfile). 7.3x slower than nx
at n=1500/E=5224.

An existing native kernel (`_fnx.read_adjlist`) was unused and unsuitable:
it double-builds (EdgeListEngine graph -> ReadWriteReport -> second
RustGraph via `report_to_pygraph`), runs Hardened mode (default
constructor path is Strict), and has an adjacency-order divergence vs the
delegated path — only ~1.4x better than delegation.

## Lever (one)

New `_fnx.read_adjlist_simple(path)` single-pass parser building the FINAL
`PyGraph` directly:

- token -> canonical id ("str:{byte_len}:{s}", matching
  `node_key_to_string`) cached per unique token;
- nodes registered in first-appearance order, edges batched, then inserted
  through `extend_nodes_unrecorded` / `extend_edges_unrecorded`
  (br-r37-c1-4jd8m bulk paths) — skipping the per-element
  `record_decision` ledger push (timestamp syscall + several String
  allocs each) which dominated per-edge construction;
- `CompatibilityMode::Strict` to byte-match what the delegated path
  builds via `fnx.Graph()`.

Python wrapper gate (readwrite._read_adjlist_via_nx): fast path only for
comments="#", delimiter=None, nodetype=None, encoding="utf-8",
create_using in (None, fnx.Graph class), str path not .gz/.bz2. The
kernel returns None (-> delegated path, exact nx error surfaces) for
missing/non-UTF-8 files and for blank/whitespace-only lines, where nx
raises IndexError("pop from empty list") (verified: nx really does raise
on those).

## Parity proof (parity_proof.py)

82/82 cases, 0 failures:
- 60 random corpus graphs (sizes 0..200, int/str/unicode/mixed labels,
  self-loops, nx-written) — fast path == nx == old delegated path on
  node ORDER, edge ORDER, adjacency ORDER, node/edge/graph attrs;
- 12 hand-crafted files (tabs, CRLF, duplicate edges both directions,
  inline comments, comment-only lines, isolated nodes, no trailing
  newline, shared targets);
- error parity (blank/ws-only/ws+comment lines, missing file);
- non-default kwargs still delegate (nodetype=int, create_using=DiGraph,
  delimiter override);
- fast-path graph mutability (G[u][v][k]=v sync, add_edge/add_node, copy).

GOLDEN_CORPUS_SHA256: 9721b8d4fadd1c72e74e7fd0b9d2f9aaae216fac01367021ac2e148528020a27
(identical across the per-edge -> bulk-path rewrite and the canon-cache
rewrite — bit-exact through both optimization steps)

## Bench (interleaved warm min-of-15, bench.py)

n=1500, E=5224 (profiled sweep size):
- before: fnx 27.7-39.5ms vs nx 4.8-6.2ms = 5.4-6.4x slower
- after:  fnx 4.8ms vs nx 4.9ms = 0.97-1.10x — parity with nx
- self-speedup: 4.9-5.9x
- small file (50 edges): 0.60x — 1.7x FASTER than nx

n=20000, E=60247: 1.66x residual — remaining cost is the per-object
PyDict mirror alloc (node_py_attrs/edge_py_attrs) substrate tax
(br-r37-c1-w1dm8 / 71x9k territory), not the parse.

Score: Impact (7.3x -> 1.0x on a public read API) x Confidence (82-case
differential + identical golden sha + 18-test committed regression suite
+ full pytest run) / Effort = well over 2.0.

## Validation

- tests/python/test_read_adjlist_native_parity.py: 18 passed
- readwrite-filtered pytest (-k "adjlist or readwrite or read_ or edgelist"): 196 passed
- full tests/python suite: 21304 passed; 6 failures pre-exist at HEAD
  (MultiGraph constructor unhashable-endpoint paths, reproduced with
  HEAD-pure tree, unrelated to this change)
- cargo clippy -p fnx-python: no new warnings (removed one unused import)
- cargo fmt --check: clean
- Built/tested in isolated worktree (HEAD + this change) because the
  shared checkout had a peer's mid-edit fnx-python compile breakage.
