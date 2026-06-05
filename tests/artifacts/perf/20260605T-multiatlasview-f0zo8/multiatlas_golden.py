#!/usr/bin/env python3
"""NetworkX parity/golden harness for br-r37-c1-f0zo8.

This artifact pins nested MultiGraph/MultiDiGraph adjacency mapping semantics.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def normalize(value):
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return [[normalize(k), normalize(v)] for k, v in value.items()]
    return value


def exc_record(func):
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - artifact records public behavior.
        return {
            "type": type(exc).__name__,
            "args": normalize(list(exc.args)),
            "str": str(exc),
        }
    return None


def assign_item(mapping):
    mapping["x"] = {}


def view_name(obj):
    return type(obj).__name__


def deep_items(view):
    return [
        [
            nbr,
            [
                [key, dict(attrs)]
                for key, attrs in keydict.items()
            ],
        ]
        for nbr, keydict in view.items()
    ]


def build_graph(module, graph_name):
    graph = getattr(module, graph_name)()
    graph.add_edge("root", "b", key=2, weight=20, label="first")
    graph.add_edge("root", "a", key=0, weight=10, label="second")
    graph.add_edge("root", "b", key=0, weight=30, label="third")
    graph.add_edge("root", "c", key="z", weight=40, label="string-key")
    if graph_name == "MultiGraph":
        graph.add_edge("d", "root", key=1, weight=50, label="undirected-inbound")
    else:
        graph.add_edge("d", "root", key=1, weight=50, label="predecessor-only")
    return graph


def record(module_name, module, graph_name):
    graph = build_graph(module, graph_name)
    view = graph["root"]
    inner_b = view["b"]
    attr_b0 = inner_b[0]
    before_mutation_id_same = attr_b0 is graph["root"]["b"][0]
    attr_b0["mutated"] = "visible"
    after_mutation_visible = graph["root"]["b"][0]["mutated"]

    live_before = list(graph["root"].keys())
    graph.add_edge("root", "late", key=7, weight=70)
    live_after_add = list(graph["root"].keys())
    graph.remove_edge("root", "late", key=7)
    live_after_remove = list(graph["root"].keys())

    outer_setitem = exc_record(lambda: assign_item(view))
    missing_outer = exc_record(lambda: graph["missing"])
    missing_inner = exc_record(lambda: graph["root"]["missing"])
    missing_key = exc_record(lambda: graph["root"]["b"]["missing-key"])

    adj_view = graph.adj["root"]
    adj_outer_setitem = exc_record(lambda: assign_item(adj_view))

    return {
        "module": module_name,
        "graph": graph_name,
        "view_type": view_name(view),
        "view_is_mapping": isinstance(view, Mapping),
        "inner_type": view_name(inner_b),
        "inner_is_mapping": isinstance(inner_b, Mapping),
        "outer_keys": list(view.keys()),
        "outer_items": deep_items(view),
        "inner_b_keys": list(inner_b.keys()),
        "inner_b_items": [[key, dict(attrs)] for key, attrs in inner_b.items()],
        "attr_dict_identity_same": before_mutation_id_same,
        "attr_mutation_visible": after_mutation_visible,
        "live_keys_before": live_before,
        "live_keys_after_add": live_after_add,
        "live_keys_after_remove": live_after_remove,
        "outer_setitem_error": outer_setitem,
        "adj_outer_setitem_error": adj_outer_setitem,
        "missing_outer_error": missing_outer,
        "missing_inner_error": missing_inner,
        "missing_key_error": missing_key,
        "repr_prefix": repr(view).split("(", 1)[0],
        "str_value": str(view),
    }


def compare_pair(graph_name):
    f_record = record("fnx", fnx, graph_name)
    n_record = record("nx", nx, graph_name)
    comparable_fields = [
        "view_is_mapping",
        "inner_is_mapping",
        "outer_keys",
        "outer_items",
        "inner_b_keys",
        "inner_b_items",
        "attr_dict_identity_same",
        "live_keys_before",
        "live_keys_after_add",
        "live_keys_after_remove",
        "missing_outer_error",
        "missing_inner_error",
        "missing_key_error",
        "repr_prefix",
        "str_value",
    ]
    mismatches = []
    for field in comparable_fields:
        if f_record[field] != n_record[field]:
            mismatches.append(
                {
                    "field": field,
                    "fnx": f_record[field],
                    "nx": n_record[field],
                }
            )
    if f_record["attr_mutation_visible"] != "visible":
        mismatches.append({"field": "fnx.attr_mutation_visible", "fnx": f_record["attr_mutation_visible"]})
    if n_record["attr_mutation_visible"] != "visible":
        mismatches.append({"field": "nx.attr_mutation_visible", "nx": n_record["attr_mutation_visible"]})
    # Both must reject assigning through the outer adjacency mapping. Exact text
    # can differ across Rust/Python implementation types.
    for field in ("outer_setitem_error", "adj_outer_setitem_error"):
        f_error = f_record[field]
        n_error = n_record[field]
        if (f_error is None) != (n_error is None):
            mismatches.append({"field": field, "fnx": f_error, "nx": n_error})
        elif f_error is not None and f_error["type"] != n_error["type"]:
            mismatches.append({"field": field, "fnx": f_record[field], "nx": n_record[field]})
    return {
        "graph": graph_name,
        "fnx": f_record,
        "nx": n_record,
        "mismatches": mismatches,
        "ok": not mismatches,
    }


def main(argv):
    output = Path(argv[0]) if argv else None
    rows = [compare_pair("MultiGraph"), compare_pair("MultiDiGraph")]
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    if output is not None:
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
