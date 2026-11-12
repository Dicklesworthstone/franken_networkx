# br-r37-c1-fhdxg Isomorphism Proof

## Changed Path

The new path is gated to exact `type(self) is MultiGraph`, exact integer endpoints, exact `type(key) is str`, no attributes, and endpoint pairs with no existing edge bucket. All other calls stay on the prior generic `MultiGraph.add_edge` implementation.

## Ordering

Node insertion order is unchanged: the fast path stores the original Python endpoint objects in the same first-seen order before inserting the edge. Edge iteration order is unchanged for fresh pairs because the Rust internal edge key remains `0`, matching the prior generic first-edge path.

## Key Semantics

The explicit Python string key is stored in `edge_py_keys` and returned to Python unchanged. String keys remain distinct from hash-equivalent-looking integer keys, so `key="7"` and `key=7` keep NetworkX dictionary semantics. Repeated pairs fall back to the generic resolver, preserving first-display-key behavior, hash/equality canonicalization, and attribute updates.

## Attributes, Directed Cases, And Subclasses

Attribute-bearing calls, existing parallel-edge buckets, subclasses, `MultiDiGraph`, non-int endpoints, and non-string keys all bypass the new string fast path. Their behavior is unchanged.

## Floating Point And RNG

This construction path performs no floating-point arithmetic and uses no RNG. Existing floating-point key lookup behavior remains on the generic resolver path.

## Golden Digest

The construction golden digest stayed unchanged:

`a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`

Focused pytest covered string-key fresh pairs, self-loops, integer-vs-string lookup distinction, repeated-pair attribute fallback, the prior int-key fast path, and non-integer multigraph edge-key round trips.
