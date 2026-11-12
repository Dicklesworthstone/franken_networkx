"""Probe: fnx.check_planarity vs nx.check_planarity over the oracle corpus."""

import json
import sys
from pathlib import Path

import networkx as nx

import franken_networkx as fnx

fixture = json.loads(
    Path(__file__).resolve().parent.parent
    .joinpath("tests/fixtures/planarity_embedding_oracle.json")
    .read_text()
)

failures = 0
for name, entry in fixture["graphs"].items():
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(entry["nodes"])
    g_fnx.add_edges_from((u, v) for u, v in entry["build_edge_order"])
    g_nx = nx.Graph()
    g_nx.add_nodes_from(entry["nodes"])
    g_nx.add_edges_from((u, v) for u, v in entry["build_edge_order"])

    fnx_r = fnx.check_planarity(g_fnx)
    nx_r = nx.check_planarity(g_nx)

    verdict = fnx_r[0] == nx_r[0]
    type_ok = type(fnx_r[1]) is type(nx_r[1])
    data = (fnx_r[1].get_data() == nx_r[1].get_data()) if fnx_r[0] else True
    ok = verdict and type_ok and data
    if not ok:
        failures += 1
        print(f"FAIL {name}: verdict={fnx_r[0]}/{nx_r[0]} type={type(fnx_r[1]).__name__}/{type(nx_r[1]).__name__}")
        if fnx_r[0] and nx_r[0]:
            fd, nd = fnx_r[1].get_data(), nx_r[1].get_data()
            for node in fd:
                if fd[node] != nd.get(node):
                    print(f"  {node}: fnx={fd[node]} nx={nd.get(node)}")

# non-graph-type inputs and extras
extra = fnx.Graph()
extra.add_node("iso")
extra.add_edges_from([("a", "b"), ("b", "c")])
r = fnx.check_planarity(extra)
print("isolated-node graph:", r[0], "| iso in embedding:", "iso" in r[1], "| a nbrs:", list(r[1]["a"]))
r2 = fnx.check_planarity(fnx.Graph())  # empty
print("empty graph:", r2[0], type(r2[1]).__name__)

print("FAILURES:", failures)
sys.exit(1 if failures else 0)
