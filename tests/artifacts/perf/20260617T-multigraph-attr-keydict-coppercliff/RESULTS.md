# br-r37-c1-ofwon MultiGraph Attributed Construction

Target: `MultiGraph.add_edges_from` on fresh exact-int `(u, v, {"weight": f64})`
construction.

Candidate: defer construction-time Python edge-attribute mirror dicts and rely on
lazy materialization from inner Rust attrs.

Verdict: rejected. The survey median improved, but the comparable profile and
process-level hyperfine regressed, so Score < 2.0 and no source change was kept.

## Baseline

- Survey `multigraph_attr` digest match: `true`
- FNX median: `0.019810931000392884s`
- NetworkX median: `0.01612607395509258s`
- FNX/NX ratio: `1.2285030476458056`
- Digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`
- Hyperfine loop120 FNX mean: `6.766129597279999s`
- Hyperfine loop120 NetworkX mean: `5.45769825048s`
- Profile total: `10.163s / 160` builds
- `_try_add_attr_edges_from_batch`: `2.840s / 160`
- `_native_edge_view_list`: `1.745s / 160`

## Candidate

- Survey `multigraph_attr` digest match: `true`
- FNX median: `0.017535138002131134s`
- NetworkX median: `0.016408652998507023s`
- FNX/NX ratio: `1.0686518877403652`
- Digest: `50644c550f48ebc209b8fa5bb649acf1961385c2b71d65f0a572cb3e2a22ae99`
- Hyperfine loop120 FNX mean: `6.999156736720001s`
- Hyperfine loop120 NetworkX mean: `6.15350248152s`
- Profile total: `10.673s / 160` builds
- `_try_add_attr_edges_from_batch`: `2.542s / 160`
- `_native_edge_view_list`: `2.747s / 160`

## Notes

The candidate moved cost from construction into first edge-data materialization.
That helps the direct survey median but hurts the digest/materialization path and
does not improve the process envelope. The next attempt should target the
post-construction `_native_edge_view_list`/digest materialization path directly
or a different MultiGraph keydict layout primitive.
