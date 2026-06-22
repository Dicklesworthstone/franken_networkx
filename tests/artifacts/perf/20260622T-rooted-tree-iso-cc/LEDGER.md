# rooted_tree_isomorphism in-process pre-reject (br-r37-c1-treeisocheck, cc)

Sibling of tree_isomorphism: delegated via 2x fnx->nx conversion + AHU even for non-iso. A rooted iso is an unrooted iso mapping root->root, so faster_could_be_isomorphic (degree seq) is a sound necessary reject. is_tree + faster_could_be now run in-process; non-iso short-circuits without converting.

0.50x -> 69.51x (n=250 random trees; fnx 0.0209ms / nx 1.4289ms). Byte-identical: NotATree contract + [] for non-iso; 0 fails vs nx (49 pairs x roots {(0,0),(1,5)} + edge cases); iso-mapping path unchanged. Full suite 49239 passed, same 5 pre-existing.
