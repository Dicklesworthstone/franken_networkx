# is_isomorphic / vf2pp_is_isomorphic faster_could_be pre-reject (br-r37-c1-isoprecheck, cc)

Both fns (no node/edge match) went straight to the VF2++ rust kernel (_is_isomorphic_rust), paying full setup (~0.2ms) before rejecting a non-isomorphic pair. Added the sound degree-histogram pre-reject faster_could_be_isomorphic first (~0.013ms; necessary condition valid for undirected/directed/multigraph). NOT could_be_isomorphic — it raises NetworkXError('not implemented for directed type'). nx's own is_isomorphic doesn't call could_be either (straight to GraphMatcher, which fast-rejects internally).

is_isomorphic 0.22x -> 4.37x; vf2pp_is_isomorphic 0.38x -> 3.68x (n=200 gnm seed1 vs seed2, warm).
Byte-exact: end-to-end 0/50 vs networkx (und+dir x iso+non-iso x both fns); soundness 0/75 gated-vs-current. Full suite 49239 passed, same 5 pre-existing. Shipped 4e1ffebe9.

Found by sweeping the un-swept isomorphism domain — corrected a premature 'fully converged' claim: off-gauntlet fns can still have missing-pre-check gaps. Sibling open items (in __init__.py): from_prufer_sequence 0.35x (construction-tax batch), tree_isomorphism 0.13x.
