# br-r37-c1-04z53.9134 star laplacian certificate

Target: `fnx.laplacian_spectrum(fnx.star_graph(798))` after the closed-form
star Laplacian bypass. The remaining profile-backed cost was the Python
star-shape detector scan.

## Lever

Store `_fnx_star_shape = (nodes_seq, edges_seq, node_count)` on exact `Graph`
objects constructed by `star_graph`, then let `laplacian_spectrum` consume that
certificate before scanning edges and degrees.

The certificate is accepted only when:

- `type(G) is Graph`
- `nodes_seq` and `edges_seq` still match the generator-time token
- the stored node count is at least 2 and still has `n - 1` edges
- `weight is None`, or the native weight-cache token reports matching mutation
  counters and no dirty edge-attribute exposure

Weighted mutations, direct edge-dict mutations, count-preserving rewires,
non-star graphs, subclasses, directed graphs, and multigraphs keep the existing
fallback route.

## Baseline

- Direct FNX median: `0.000887321017216891s`
- Direct NetworkX median: `0.03070563799701631s`
- 1000-call cProfile: `1.2839305800152943s`
- Local hyperfine, 1000 FNX calls: mean `1.2628614375400002s`
- Golden sorted q9 SHA: `375fa52a42b6385d40091801807090bb18b6061ea6d5584bec0005bad4e5415e`

## After

- Direct FNX median: `0.00035568297607824206s`
- Direct NetworkX median: `0.031952128978446126s`
- 1000-call cProfile: `0.6055148189770989s`
- Local hyperfine, 1000 FNX calls: mean `0.6359370012400001s`
- Golden sorted q9 SHA: `375fa52a42b6385d40091801807090bb18b6061ea6d5584bec0005bad4e5415e`

## Delta

- Direct median speedup: `2.4946963360475842x`
- Profile speedup: `2.1203949759384066x`
- Hyperfine mean speedup: `1.9858278965960048x`
- Max sorted delta FNX vs NetworkX: `1.887379141862766e-14`
- Max sorted delta FNX vs closed form: `0.0`

## Validation

- Focused pytest: `tests/python/test_laplacian_spectrum_native.py -k 'star_laplacian or laplacian_spectrum' -q` -> `24 passed`
- Py compile: `python/franken_networkx/__init__.py` and focused spectrum test passed
- `cargo fmt --check` passed
- `cargo check -p fnx-python --all-targets` passed
- `cargo clippy -p fnx-python --all-targets -- -D warnings` passed
- `git diff --check` passed
- `ubs python/franken_networkx/__init__.py tests/python/test_laplacian_spectrum_native.py` was bounded with `timeout 180s`; it timed out after starting the Python scan with no findings emitted

## Score

Impact `4` x Confidence `5` / Effort `1` = `20.0`; keep.
