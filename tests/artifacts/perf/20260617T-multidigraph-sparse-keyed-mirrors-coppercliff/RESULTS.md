# br-r37-c1-mofy1 MultiDiGraph Sparse Keyed Mirrors

Target: `MultiDiGraph.add_edges_from` on fresh exact-int
`(u, v, {"weight": f64})` attributed construction.

Candidate: avoid construction-time Python keyed-edge attribute mirror dicts for
fresh exact-int `MultiDiGraph` batches, and materialize those mirrors lazily from
the inner Rust edge attrs when keyed edge views need them.

Verdict: rejected. The construction micro-path improved, but comparable total
profile time and process-level hyperfine regressed, so Score < 2.0 and no source
change was kept.

## Baseline

- Survey `multidigraph_attr` digest match: `true`
- FNX median: `0.024428890959825367s`
- NetworkX median: `0.016990987001918256s`
- FNX/NX ratio: `1.4377558500319836`
- Digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`
- Hyperfine loop50 FNX mean: `2.682680848725s`
- Hyperfine loop50 NetworkX mean: `2.3826198806s`
- Profile total: `9.719s / 160` builds
- `_try_add_attr_edges_from_batch`: `3.094s / 160`
- edge-data materialization `__call__`: `1.105s / 160`

## Candidate

- Survey `multidigraph_attr` digest match: `true`
- FNX median: `0.017044903011992574s`
- NetworkX median: `0.01630482100881636s`
- FNX/NX ratio: `1.0453903788809478`
- Digest: `58267b72563bb3af74585c8d9d4e4dc2e46cbb5f253675efdebda5ea12604b24`
- Hyperfine loop50 FNX mean: `2.82802599706s`
- Hyperfine loop50 NetworkX mean: `2.4169445900600004s`
- Profile total: `9.975s / 160` builds
- `_try_add_attr_edges_from_batch`: `2.617s / 160`
- edge-data materialization `__call__`: `1.835s / 160`

## Notes

The candidate moved work out of construction and into first keyed edge-data
materialization. Since the benchmark/digest path observes edge attrs after
construction, the deferred work made the total envelope slower despite a faster
insertion primitive. The next attempt should target edge-data materialization
itself or replace the keyed-edge attr layout rather than deferring the existing
dict construction.
