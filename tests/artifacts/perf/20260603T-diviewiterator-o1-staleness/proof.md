# DiViewIterator O(1) staleness check (br-r37-c1-divit)

DiViewIterator::__next__ (crates/fnx-python/src/digraph.rs) rebuilt
`g.inner.nodes_ordered()` (an O(N) Vec) and compared every element on EVERY
next() -> O(N^2) to iterate any DiGraph view (nodes/edges/degree). The
undirected NodeViewIterator already uses an O(1) node_count + nodes_seq snapshot
(br-gauntlet-perf-nodeviewiter); the DiGraph iterator was missed.

Ported the same O(1) check: snapshot expected_count + expected_seq; in __next__,
`if g.nodes_seq != expected_seq { disambiguate size-vs-keys via node_count }`.
Also dropped the now-pointless per-call nodes_ordered() Vec build in
DiEdgeView::__iter__.

Isomorphism: add_node/remove_node bumps nodes_seq (seq change <=> node-set
change), so the SAME mutations are detected with the SAME Python-dict error
wording ("changed size" vs "keys changed") -- this is the exact logic the
undirected views already ship and are tested against. Output of
nodes()/edges()/in_degree()/out_degree() is bit-identical to networkx (0
failures, 3 directed graphs incl. order); mutate-during-iteration still raises
for edges()+nodes(); clean iteration does not raise. 3677 directed/iteration
pytest cases + clippy -D warnings pass.

    DIVIT_GOLDEN 750b235c09ad44171d454219f042fdd3ff491ae50bd007b0d7b637bc8cfb71a3

Bench (DiGraph nodes() on gnp(1200,0.006,directed), min-of-60, load-robust):
    before: 4.439 ms
    after : 0.140 ms   -> 31.7x

(edges()/in_degree() are unchanged -- materialization-bound, a separate lever;
this fix also future-proofs every DiView iterator against the O(N^2) blowup.)
Opportunity Score = Impact 5 x Confidence 5 / Effort 2 = 12.5.
