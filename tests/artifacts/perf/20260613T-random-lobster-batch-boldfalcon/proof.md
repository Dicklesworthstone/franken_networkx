# br-r37-c1-04z53.82 Proof

## Target

- Function: `random_lobster_graph(n=800, p1=0.35, p2=0.7, seed=11)`.
- Profile-backed hotspot: baseline cProfile spent the run in `random_lobster`,
  with `1347` Python `Graph.add_edge` calls and `7907` total calls.
- Alien-graveyard primitive: batch the generated edge stream so the hot path
  crosses the Python/native graph boundary once instead of once per edge.

## Lever

The generator now appends generated lobster edges to `lobster_edges` in the
same loop positions where it previously called `graph.add_edge`, then performs
one `graph.add_edges_from(lobster_edges)` after the loops. The path backbone is
still created by the existing `path_graph(backbone_length)` call.

## Isomorphism Proof

- RNG: unchanged. The same `rng.random()` calls occur in the same loop order;
  no graph mutation or graph query affects control flow between random draws.
- Ordering: unchanged. Each tuple is appended exactly where the old code added
  that edge, and `add_edges_from` consumes the list in append order.
- Tie-breaking: not applicable beyond insertion order; the generated node IDs
  and edge order remain identical.
- Floating point: unchanged. The only floating-point operations are the same
  `backbone_length` computation and the same probability comparisons.
- Graph state: the loop never reads the graph after adding an edge. Delaying
  edge insertion until after generation cannot change subsequent decisions.
- `create_using`: unchanged. The copy into a requested graph type still happens
  after all generated edges are present in `graph`.

## Golden Verification

- Baseline FNX SHA:
  `8cdf191df927b2f4bdaa38bc8070e67af67f329b74355474a97b3350cd057749`.
- Candidate FNX SHA:
  `8cdf191df927b2f4bdaa38bc8070e67af67f329b74355474a97b3350cd057749`.
- NetworkX SHA before/after:
  `8cdf191df927b2f4bdaa38bc8070e67af67f329b74355474a97b3350cd057749`.
- Shape: `2071` nodes, `2070` edges.
- Focused direct parity: `5` cases passed, SHA
  `0b319508c313384867b5c29a791f50479989a5953df543e212ba07b75f8113d8`.

## Benchmarks

- Direct FNX median:
  `0.0032624199957353994s -> 0.001735889003612101s`
  (`1.8793943558296855x`).
- Direct FNX mean:
  `0.0034621489499042537s -> 0.0019115092670800528s`
  (`1.811212223518486x`).
- Hyperfine loop10 mean:
  `0.33947073084s -> 0.31413170908000004s`
  (`1.0806636866880155x`).
- Hyperfine loop10 median:
  `0.33997316024s -> 0.31881810278s`
  (`1.0663546306672493x`).
- Profile mechanism:
  `7907 -> 3842` total calls; per-edge Python `Graph.add_edge` calls
  `1347 -> 0`; one `add_edges_from` batch remains.

## Score

`Impact x Confidence / Effort = 1.8793943558296855 x 4 / 1 = 7.517577423318742`.
Decision: keep.

## Validation

- `PYTHONPATH=python python3 -m py_compile python/franken_networkx/__init__.py`
  passed.
- Focused pytest for lobster/shell generator parity and dispatch passed:
  `5 passed in 0.46s`.
- Direct parity probe passed: `5` cases, SHA
  `0b319508c313384867b5c29a791f50479989a5953df543e212ba07b75f8113d8`.
- `rch exec -- cargo check -p fnx-python --lib` passed on `vmi1156319`.
- `git diff --check` passed.
- `ubs python/franken_networkx/__init__.py` timed out after `90s` with no
  findings emitted.
- Known pre-existing validation noise remains outside this lever:
  `fnx-generators` unused-return warnings and earlier workspace rustfmt drift.
