# br-r37-c1-opxj0 weighted all_pairs_dijkstra proof

Target: profile-backed `all_pairs_dijkstra_weighted` from
`bench_delegation_goldmines.py`.

One lever: route explicit non-unit weighted `all_pairs_dijkstra` calls through
the exact NetworkX parity path, leaving missing/default-unit-weight native calls
on the existing Rust raw path.

Behavior proof:

- Ordering and tie-breaking: delegated output is emitted by
  `networkx.all_pairs_dijkstra`, so outer node order, inner finalize order, and
  equal-distance heap tie behavior are exactly NetworkX's behavior.
- Floating point: no arithmetic is changed in FrankenNetworkX; NetworkX performs
  the weighted Dijkstra arithmetic for this gated path.
- RNG: none.
- Type parity: the previous raw path compared value-equal to NetworkX but
  emitted source self-distance as `float:0.0`; the parity path emits
  NetworkX's `int:0`, making stable digest output byte-identical.

Golden SHA-256 evidence:

- n=80: `b799b17c9a68d0dc3e2f969a4a08636207d9d6fbb00eb30026e643fccbe913a7`
- n=300: `c484210132d85854ae36c4012c3e8087f869a136049c99dca4ac175fd88b9e99`
- n=500: `b285935a8d9756da8fdbd9a1608dda42bb4fb699e1ead3b434158ff097134740`

Benchmark evidence:

- rch hyperfine broad harness: `2.9913864211s +/- 0.2245989965s` to
  `2.68337500294s +/- 0.0516792461s`.
- rch direct raw-private to public parity path:
  - n=80: `0.0235610100s -> 0.0106003789s` (`2.22x`)
  - n=300: `0.8422800470s -> 0.2232892700s` (`3.77x`)
  - n=500: `3.5418560388s -> 0.9051202990s` (`3.91x`)
- Post-change public FNX digest matches NetworkX on the harness:
  `digests_match=true`, FNX mean `0.0100281908s`, NetworkX mean
  `0.00873836845s`.

Validation:

- `rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_all_pairs_dijkstra_inner_order_parity.py tests/python/test_all_pairs_dijkstra_outer_order_parity.py tests/python/test_more_all_pairs_outer_order_parity.py tests/python/test_dijkstra_finalize_order_parity.py tests/python/test_shortest_path.py -k all_pairs_dijkstra -q`
