# Isomorphism Proof

The candidate was reverted because it did not clear Score >= 2.0. While tested, it preserved behavior by using the same `_native_in_edges_data_key(weight, default_weight)` values, the same topological order, the same stable predecessor-order `max`, the same negative-distance reset, and the same Python numeric operations as `dag_longest_path`.

Golden SHA stayed identical for baseline FNX, NetworkX oracle, candidate FNX, and restored FNX:

`34f3f915ca217ba76be7da282e59e7c1eddf322628c011cb634db0c7b0c4b4fb`

The source tree was restored to `HEAD` for `python/franken_networkx/__init__.py`; no code change is kept from this rejected lever.

