# tree_isomorphism in-process pre-reject (br-r37-c1-treeisocheck, cc)

tree_isomorphism delegated to nx via a 2x whole-graph fnx->nx conversion even for non-isomorphic trees. nx's own tree_isomorphism rejects non-iso in O(n) via is_tree + faster_could_be_isomorphic (degree sequence) BEFORE the AHU — but the delegate paid the conversion first. Now run those cheap checks in-process on the fnx trees; non-iso short-circuits without converting (39/39 random distinct trees differ in degree seq). Isomorphic-mapping path unchanged (still delegate).

0.13x -> 10.05x (n=300 random trees, warm; fnx 0.0247ms / nx 0.2465ms). Byte-identical: NotATree contract, [] for non-iso; 0 fails / 64 pairs + edge cases (single/two-node, iso, non-tree-raise, diff-size, star-vs-path) vs nx. Full suite 49239 passed, same 5 pre-existing.
