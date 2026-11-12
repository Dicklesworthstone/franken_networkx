Isomorphism proof: weighted Hyper-Wiener native path
====================================================

Behavior surface
----------------

The native path is only used when all of these are true:

- graph is not directed;
- graph is not a multigraph;
- graph is non-empty and connected;
- `weight` is a string attribute name;
- existing weight values are finite numeric nonnegative values.

All other public surfaces continue through the existing NetworkX parity
delegation path.

Ordering and tie-breaking
-------------------------

`hyper_wiener_index` returns a scalar, not an ordered collection. The weighted
kernel sums over `nodes_ordered()` with `s < t`, matching the unordered-pair
contract. Dijkstra predecessor tie-breaking is not observable because only
shortest-path distances contribute to `d + d*d`; equal-distance path ties do
not affect the scalar.

Floating point
--------------

The fast path preserves NetworkX's weighted shortest-path semantics for finite
nonnegative numeric weights. Missing edge weights default to `1.0` through the
existing Dijkstra helper. Non-finite and nonnumeric weights are screened by the
Python wrapper and delegated to NetworkX, preserving exception behavior.

RNG
---

No RNG participates in the implementation. The benchmark and proof fixtures are
deterministic.

Golden hashes
-------------

The golden proof hash is unchanged:

- baseline:
  `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`;
- final:
  `749835d34930e6e683bcb69d4b6aea8d27f1327bb4bc976e534053849cab834b`.

The final weighted bench also records matching FNX/NetworkX scalar digests for
the 80-node weighted fixture.

