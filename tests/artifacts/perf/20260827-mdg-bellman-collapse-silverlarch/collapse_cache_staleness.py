"""The blocker a collapse cache would hit (br-r37-c1-mg7hw).

Caching _multigraph_collapse_min_weight_bellman against a revision token is the strongest
route on this operation - a cache hit costs 15,256,361 Ir/call against networkx's
20,060,386, i.e. 1.315x, where recomputing the collapse every call costs 55,129,849 and
loses at 0.364x. It is also correctness-neutral in principle: the same collapse, computed
less often.

The obvious key is (nodes_seq, edges_seq), and it is NOT SAFE. Neither token observes an
in-place edge-attribute write, so a cache keyed on them serves a stale length after an
ordinary weight assignment. That is the br-r37-c1-txkrn class, where a row cache outlived
the map it mirrored and produced five wrong-answer manifestations.

Run: PYTHONPATH=python python3 collapse_cache_staleness.py
"""

import franken_networkx as fnx


def tokens(graph):
    return (graph.nodes_seq, graph.edges_seq)


g = fnx.MultiDiGraph()
g.add_edge("a", "b", weight=1.0)
g.add_edge("b", "c", weight=2.0)

before_tokens = tokens(g)
before_length = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")

# An ordinary in-place weight write - no node or edge is added or removed.
g["a"]["b"][0]["weight"] = 99.0

after_tokens = tokens(g)
after_length = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")

print(f"tokens before write : {before_tokens}")
print(f"tokens after  write : {after_tokens}")
print(f"length before write : {before_length}")
print(f"length after  write : {after_length}")
print()
if before_tokens == after_tokens and before_length != after_length:
    print("BLOCKER CONFIRMED: the revision tokens are UNCHANGED while the correct answer")
    print("moved. A collapse cached on (nodes_seq, edges_seq) would return the stale")
    print(f"length {before_length} here instead of {after_length}.")
    print()
    print("A safe cache needs a token that bumps on ATTRIBUTE writes, or the store's")
    print("edge-dirty tracking. Whichever is chosen, make this case fail on the unfixed")
    print("arm before landing the fix - a guard never seen to fail is not a guard.")
else:
    print("Tokens now track attribute writes; re-check whether this blocker still applies.")
