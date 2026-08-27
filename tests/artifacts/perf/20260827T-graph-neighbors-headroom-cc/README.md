# `Graph.neighbors(n)` — 40ns of headroom, but the obvious lever is REFUTED (br-r37-c1-nbrhead)

**Verdict: NOT taken this cycle. No code change. The clear hypothesis was measured
and refuted; what remains is speculative Rust with a ceiling BELOW parity.**

This is deliberately NOT the same verdict as
`20260827T-multigraph-row-len-NEGATIVE-cc`. That row was rejected because it is
at the crossing floor and NO native can help. This one has real headroom. It is
being left open with the budget quantified, not declared impossible.

## Where it ranks

Broad 90-row survey against LIVE networkx on HEAD (75/90 decidable, 21 below 1.0):

    0.5692x  MultiGraph   G[u] bulk         <- floor-bound, already rejected
    0.6576x  MultiDiGraph G[u] bulk         <- same defect
    0.8362x  Graph        G.neighbors bulk  <- THIS ROW
    0.8612x  DiGraph      G[u] bulk
    0.8854x  MultiGraph   G.neighbors bulk

`MultiDiGraph build add_edges_from` (0.6696x in the previous survey) has dropped
off the list entirely — closed by br-r37-c1-mgaefgen.

## It is the CALL, not the drain

    sum(len(list(G.neighbors(n))))   nx  64.65us  fnx  76.44us   0.8458x
      neighbors() only               nx  21.04us  fnx  29.24us   0.7195x  <- here
      list(it) drain                 nx  15.27us  fnx  15.19us   1.0053x

## Headroom is real — 40ns, unlike the rejected row

    Graph, per call (ns)
      networkx  G.neighbors(0)                 86.2
      fnx       G.neighbors(0)                112.2
      fnx       has_node(0)   [minimal 1-arg]  72.1   <- crossing floor
      fnx       number_of_nodes() [0-arg]      52.9

fnx sits 40ns ABOVE its own one-arg crossing floor, so there is attackable work.
Compare the rejected `len(G[u])` row, where fnx was AT the floor (119.8ns against
a 122.1ns floor) and networkx's whole call was cheaper than any crossing.

## REFUTED: an int-key fast path

The obvious lever — an identity-int path skipping canonicalization, as `has_edge`
carries — buys NOTHING here. Int and str keys cost the same:

    int keys   nx  86.2ns   fnx 112.2ns
    str keys   nx  85.7ns   fnx 112.7ns

Canonicalization is therefore not the cost. Measured BEFORE any build was spent.

## What the 40ns actually is

`native_neighbors_iter` -> `neighbor_key_row` warm path:

  1. `require_hashable_node_key(n)`            — hashes the node
  2. `slf.borrow()` + `has_private_override()` — RefCell borrow
  3. `slf.borrow_mut()`                        — second RefCell borrow
  4. `node_key_can_use_index_lookaside(node)`  — type checks
  5. `cached_exact_string_node_index(py, node)`— hashes the node AGAIN
  6. `neighbor_key_rows_by_index.get(&index)`  — HashMap probe + nodes_seq check
  7. `row.clone_ref(py)`                       — refcount bump

networkx does ONE hash, as part of `iter(self._adj[n])`.

The only clearly redundant item is the DOUBLE HASH at (1) and (5): if the cached
index probe already raises TypeError for an unhashable key, the explicit guard is
redundant on the warm path. Worth perhaps 15-20ns.

## Why it was not taken

Removing the redundant hash lands around 92-97ns against networkx's 86ns — about
0.89-0.93x, still a LOSS. Crossing parity needs the `dict_keyiterator` contract
(br-r37-c1-nbritype) relaxed, because producing that type requires materialising
a real dict; that is a contract change, not an optimisation. A two-build cycle
for a change that stays below parity, on a hypothesis that is unverified, was
judged not worth it THIS cycle — but the budget is now quantified so the next
attempt can be judged against it.

## Provenance

    bench_elf_sha256=8c6df2c8806ead4fe14644666de2336be417d65e43311cb3242c1cca9c794987
    PYTHONPATH=$S/now2 FNX_ARM=now2 .venv/bin/python survey_broad.py
