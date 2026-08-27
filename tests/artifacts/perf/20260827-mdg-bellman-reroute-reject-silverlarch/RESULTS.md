# REJECT: rerouting MultiDiGraph bellman_ford_path_length to the raw kernel is 1.24x cheaper and WRONG (br-r37-c1-mg7hw)

SilverLarch, 2026-08-27. No code shipped beyond a parity lock.

## The candidate, and why it was tempting

46ec53c90 attributed the MultiDiGraph bellman_ford_path_length loss (0.364x vs networkx)
to a per-call collapse: _multigraph_collapse_min_weight_bellman builds a whole new simple
graph on every call and costs 41,524,156 of the 55,129,849 Ir/call, 75.3%. The native
_raw_bellman_ford_path_length accepts a MultiDiGraph directly and returns the same answer
on an ordinary fixture, at 44,296,504 Ir/call - 1.24x cheaper, available with a Python-only
change and no Rust build.

## Why it is rejected

The collapse is not purely an optimization; it carries weight validation the raw kernel has
no notion of. Run parity_bellman.py: 18 rows, three arms (networkx as reference, fnx's
public wrapper, the raw kernel as candidate), comparing exception ARGS and not just types,
because a type-only sweep reports false green.

    public wrapper divergences from networkx:   0 of 18
    raw kernel   divergences from networkx:    12 of 18

Four of the twelve are SILENT WRONG ANSWERS, which is the disqualifying kind:

    nan weight           nx raises NetworkXNoPath      raw returns 2.0
    inf weight           nx raises NetworkXNoPath      raw returns 2.0
    non-numeric weight   nx raises TypeError           raw returns 2.0
    neg inf weight       nx returns -inf               raw returns 2.0

The raw kernel simply does not see the bad weight. The remaining eight are type and message
regressions:

    plain int            nx 3     raw 3.0      (the int-vs-float length type nx preserves)
    missing weight attr  nx 2     raw 2.0
    source == target     nx 0     raw 0.0
    bool weight          nx 2     raw 2.0
    negative cycle       nx "Negative cycle detected."  raw "Negative cost cycle detected."
    unreachable target   nx "node z not reachable from a"
                         raw "No path between str:1:a and str:1:z."
    missing source       nx "Source zz not in G"        raw "Source 'zz' is not in G"
    missing target       nx raises NetworkXNoPath       raw raises NodeNotFound

The unreachable-target row leaks the CANONICAL KEY into a user-facing message - the
br-r37-c1-rmzr6 defect class, which was fixed for the dijkstra length variant and is still
present in the raw bellman kernel. It is latent, not live: nothing routes to that kernel
today, and the public wrapper is correct on all 18 rows.

## What shipped instead

tests/python/test_multidigraph_bellman_ford_weight_contract_parity.py, 18 rows, green on
HEAD. It locks the CONTRACT the collapse provides rather than the collapse itself, so any
future cheaper multigraph branch - a collapse cached against a revision token, or a native
multigraph kernel taught weight validation - is free to land as long as those rows stay
green. The divergence table above is the proof the guard actually fails on the
implementation it forbids; a guard that has never been seen to fail is not a guard.

## What this does NOT settle

The loss is real and unfixed: 55.1M Ir/call against networkx's 20.1M. The cheap reroute is
now closed, and with it the only route that needed no build. What remains is either
  * a collapse cached against the graph's revision token, which can recover at most
    55.1M -> 44.3M since the raw multigraph path costs 44.3M, or
  * the root defect - the native kernel costs ~13.6M on the collapsed simple graph against
    44.3M on the multigraph, 3.3x - which needs a Rust change and would have to learn the
    NaN/inf/non-numeric validation the collapse currently performs.

## Reproduce

    PYTHONPATH=python python3 parity_bellman.py

Prints the three-arm table and the divergence list. The Ir figures come from
tests/artifacts/perf/20260827-mdg-bellman-collapse-silverlarch/.
