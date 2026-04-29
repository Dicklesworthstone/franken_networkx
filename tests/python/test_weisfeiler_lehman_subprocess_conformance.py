"""Subprocess conformance for Weisfeiler-Lehman graph hashing."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - test harness runs a fixed local interpreter.
import sys
import textwrap


def _base_graph_specs():
    return [
        {"kind": "Graph", "nodes": [], "edges": []},
        {"kind": "Graph", "nodes": [[0, {"color": "red", "size": 1}]], "edges": []},
        {
            "kind": "Graph",
            "nodes": [[0, {"color": "red"}], [1, {"color": "blue"}]],
            "edges": [[0, 1, {"label": "ab", "weight": 2}]],
        },
        {
            "kind": "Graph",
            "nodes": [[0, {"color": "red"}], [1, {"color": "red"}], [2, {"color": "blue"}]],
            "edges": [[0, 1, {"label": "x"}], [1, 2, {"label": "y"}]],
        },
        {
            "kind": "Graph",
            "nodes": [[0, {"size": 1}], [1, {"size": 2}], [2, {"size": 3}], [3, {"size": 4}]],
            "edges": [
                [0, 1, {"weight": 1}],
                [1, 2, {"weight": 2}],
                [2, 3, {"weight": 3}],
                [3, 0, {"weight": 4}],
            ],
        },
        {
            "kind": "Graph",
            "nodes": [[0, {}], [1, {}], [2, {}], [3, {}], [4, {}]],
            "edges": [[0, 1, {}], [0, 2, {}], [0, 3, {}], [0, 4, {}]],
        },
        {
            "kind": "Graph",
            "nodes": [["a", {"color": "green"}], ["b", {"color": "green"}], ["c", {"color": "gold"}]],
            "edges": [["a", "b", {"label": "same"}], ["b", "c", {"label": "diff"}], ["c", "a", {"label": "diff"}]],
        },
        {
            "kind": "DiGraph",
            "nodes": [[0, {"color": "red"}], [1, {"color": "blue"}], [2, {"color": "red"}]],
            "edges": [[0, 1, {"label": "f"}], [1, 2, {"label": "f"}], [2, 0, {"label": "back"}]],
        },
        {
            "kind": "DiGraph",
            "nodes": [["root", {"size": 10}], ["left", {"size": 2}], ["right", {"size": 2}]],
            "edges": [["root", "left", {"weight": 1}], ["root", "right", {"weight": 1}]],
        },
        {
            "kind": "Graph",
            "nodes": [[0, {"color": "red"}], [1, {}], [2, {"color": "blue"}]],
            "edges": [[0, 1, {"label": "present"}], [1, 2, {}]],
        },
    ]


def _cases():
    option_sets = [
        {"iterations": 1, "digest_size": 8},
        {"iterations": 2, "digest_size": 16},
        {"iterations": 3, "digest_size": 20},
        {"iterations": 2, "digest_size": 16, "node_attr": "color"},
        {"iterations": 2, "digest_size": 16, "edge_attr": "label"},
        {"iterations": 2, "digest_size": 16, "node_attr": "size", "edge_attr": "weight"},
    ]
    cases = []
    for spec in _base_graph_specs():
        for options in option_sets:
            cases.append({"graph": spec, "options": options})
    return cases


_WORKER = textwrap.dedent(
    """
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    if payload["module"] == "networkx":
        import networkx as graphlib
    elif payload["module"] == "franken_networkx":
        import franken_networkx as graphlib
    else:
        raise AssertionError(payload["module"])

    def build_graph(spec):
        graph = getattr(graphlib, spec["kind"])()
        for node, attrs in spec["nodes"]:
            graph.add_node(node, **attrs)
        for left, right, attrs in spec["edges"]:
            graph.add_edge(left, right, **attrs)
        return graph

    def canonical(value):
        if isinstance(value, dict):
            return [[repr(key), canonical(item)] for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))]
        if isinstance(value, (list, tuple)):
            return [canonical(item) for item in value]
        return value

    results = []
    for case in payload["cases"]:
        graph = build_graph(case["graph"])
        options = case["options"]
        for function_name in ("weisfeiler_lehman_graph_hash", "weisfeiler_lehman_subgraph_hashes"):
            call_options = dict(options)
            if function_name == "weisfeiler_lehman_graph_hash":
                call_options.pop("include_initial_labels", None)
            else:
                call_options["include_initial_labels"] = False
            try:
                value = getattr(graphlib, function_name)(graph, **call_options)
            except Exception as exc:
                results.append({"case": case, "function": function_name, "error": [type(exc).__name__, str(exc)]})
            else:
                results.append({"case": case, "function": function_name, "value": canonical(value)})

    print(json.dumps(results, sort_keys=True))
    """,
)


def _run_worker(module_name, cases):
    proc = subprocess.run(  # nosec B603 - argv is static and shell=False.
        [sys.executable, "-c", _WORKER],
        input=json.dumps({"module": module_name, "cases": cases}),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    decoder = json.JSONDecoder()
    try:
        return decoder.decode(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"{module_name} worker returned invalid JSON:\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}",
        ) from exc


def test_weisfeiler_lehman_hashes_match_networkx_in_subprocesses():
    cases = _cases()
    assert len(cases) >= 50

    actual = _run_worker("franken_networkx", cases)
    expected = _run_worker("networkx", cases)

    assert actual == expected
