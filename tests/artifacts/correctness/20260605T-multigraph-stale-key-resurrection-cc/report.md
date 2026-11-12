# br-r37-c1-0a0uo — MultiGraph non-emptying removal resurrects stale edge attrs

Date: 2026-06-05 · Agent: cc (BlackThrush)

## Bug
PyMultiGraph::remove_edge purged the attrs/keys mirrors ONLY in the
bucket-emptying branch (br-r37-c1-kuxuc). Removing one parallel key while
others survive left the removed key's `edge_py_attrs` entry in place; a
later add_edge reusing that internal slot silently resurrected the old
attrs.

Minimal repro (was diverging, now matches nx):
    g.add_edge(4, 3); g.add_edge(4, 3, weight=7)
    g.remove_edge(4, 3)        # removes key 1 (weighted), key 0 survives
    g.add_edge(4, 3)           # fnx resurrected weight=7 on key 1

remove_edges_from routes through remove_edge -> same fix. MultiDiGraph
already had the targeted remove_edge_metadata call (clean, probed).

## Fix
Call remove_edge_metadata(u, v, removed_internal_key) unconditionally
after a successful removal; the kuxuc exhaustive purge stays for the
emptied-pair case.

## Proof
- committed metamorphic test [True-False]: 3/250 seeds diverged -> 0/250;
  test now passes all 4 parametrizations.
- extended sweep 4 classes x 1500 seeds: only residual is seed 1157
  (False,True) which step-replays to subgraph().copy() adjacency
  ROW-ORDER — the open br-r37-c1-0ek49 family, evidence attached there.
- 4 new param cases in test_multigraph_removal_purges_mirror_entries
  (incl. keyed non-last removal latent slot + reversed-orientation readd).
- full pytest: 21489 passed, 4 failures = pre-existing set minus the
  metamorphic one this fixes.
