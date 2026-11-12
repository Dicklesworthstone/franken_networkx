# br-r37-c1-zt6lj - write_adjlist native body keep

## Target

`write_adjlist` on a simple undirected graph with `n=3000`, `edges=9000`,
`seed=7`, default `comments="#"`, `delimiter=" "`, `encoding="utf-8"`.

## Lever

Emit the NetworkX-compatible comment header in Python, then use the existing
native `_rust_write_adjlist` body writer when the graph is an exact
`fnx.Graph` or `fnx.DiGraph` and `_native_adjlist_canonical_body_safe()` is
true. Multigraphs, subclass/views, custom delimiters/comments/encodings, and
non-canonical node surfaces keep the existing Python `generate_adjlist` path.

## Proof

- Ordering preserved: yes. The native body is gated by the graph's canonical
  body predicate and verified against NetworkX body order.
- Tie-breaking unchanged: yes. Source and neighbor order are compared by body
  SHA.
- Floating-point: N/A.
- RNG: fixed benchmark graph seed `7`; writer has no RNG.
- Golden SHA: `8718f5871e0f1b2d714558485ef64e2ca57b4bab7ac5303cbb52e1ac7184c941`
  for both `fnx` and `nx` bodies.

## Benchmarks

Hyperfine, warmup 3, runs 10, 20 writes per run.

| Run | Mean |
| --- | ---: |
| release baseline fnx | 0.4637s |
| release after fnx | 0.3548s |
| current after fnx | 0.3780s |
| release baseline nx | 0.4965s |

The current after rerun is 1.23x faster than the release baseline and 1.31x
faster in the original paired release evidence. Score: Impact 2 x Confidence 4
/ Effort 2 = 4.0.

## Validation

- `rch exec -- .venv/bin/python -m pytest tests/python/test_io.py::TestAdjlistIO::test_write_adjlist_default_delegates_for_byte_parity tests/python/test_io.py::TestAdjlistIO::test_write_adjlist_non_default_kwargs_stay_delegated tests/python/test_review_mode_regression_lock.py::test_write_adjlist_byte_parity_with_nx tests/python/test_review_mode_regression_lock.py::test_write_adjlist_empty_graph_has_no_extra_body_line tests/python/test_review_mode_regression_lock.py::test_write_adjlist_custom_python_key_fallback_parity -q`
- Result: `5 passed in 0.53s`.
