# br-r37-c1-fegdl: MultiGraph to_dict_of_dicts row-template cache

## Target

After `br-r37-c1-91hlu`, exact `MultiGraph` and `MultiDiGraph`
`to_dict_of_dicts(G)` calls still rebuilt the default-nodelist result rows on
every call. The remaining target frame was `_native_to_dict_of_dicts_live`.

## Baseline

- Direct `MultiGraph`: `0.10442021198105067s`, FNX/NX ratio `9.18x`
- Direct `MultiDiGraph`: `0.05354855896439403s`, FNX/NX ratio `4.65x`
- Inline hyperfine `MultiGraph`: FNX `0.5640221405400001s`, NX `0.23659262214000001s`
- Inline hyperfine `MultiDiGraph`: FNX `0.5194341358s`, NX `0.21411117350000003s`

## Lever

Added a mutation-stamped row-template cache for default-nodelist,
`edge_data is None` multigraph `to_dict_of_dicts` calls. The first call at a
given `(nodes_seq, edges_seq)` stamp uses the native row builder and stores row
templates. Later calls return a fresh outer dict and fresh row dicts by shallow
copying those templates, preserving NetworkX's contract that repeated calls
share the inner multiedge keydict object but not the returned outer or row
dicts.

Custom `nodelist`, `edge_data`, subclasses, and non-multigraph paths keep the
existing behavior.

## After

- Direct `MultiGraph`: `0.10442021198105067s -> 0.026915935100987554s` (`3.88x`)
- Direct `MultiDiGraph`: `0.05354855896439403s -> 0.01996218296699226s` (`2.68x`)
- Inline hyperfine `MultiGraph`: `0.5640221405400001s -> 0.46780041484s` (`1.21x`)
- Inline hyperfine `MultiDiGraph`: `0.5194341358s -> 0.4635866684800001s` (`1.12x`)

## Proof

- After proof payload SHA: `fbeaf80cd2707ff1bccacbb3b7800fc590d15155f36e17900a056b66c181ed04`
- After proof file SHA: `475ff66df9b2979a2772095286dfcbd0409fa787900d9ef0cea52f2ae2e3359d`
- `MultiGraph` content SHA stayed equal to NetworkX: `f3f618435f124c2651b2a5f55f587102ae83f147033c0d6aa485eaaa42eb37e3`
- `MultiDiGraph` content SHA stayed equal to NetworkX: `b3162fd60c2d4fe801bf2586bfd3b2bdf67b8b38a9c7036d7e233a477f077b42`
- Returned outer and row dict identities remain fresh across calls.
- Inner multiedge keydict identity remains shared across repeated calls.
- Mutating the graph invalidates the cache through `(nodes_seq, edges_seq)`.
- Live edge-attribute mutation remains visible through returned keydict views.
- Floating point: N/A.
- RNG: N/A.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py`
- Focused parity: `386 passed`
- Direct fresh-row/shared-inner identity and mutation invalidation probe passed
- No Rust source changed; no `rch` build was needed for this lever

Score: `4.0` (`Impact 4 * Confidence 4 / Effort 4`). Keep.

Residual route: reprofile. If this surface remains hot, use a deeper
mutation-maintained persistent keydict mirror rather than another Python
branch-shape tweak.
