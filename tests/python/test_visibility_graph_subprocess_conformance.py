"""Subprocess conformance for ``visibility_graph``.

Runs FrankenNetworkX and NetworkX in separate Python interpreters so the
oracle cannot share module state with the implementation under test.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 - test harness runs a fixed local interpreter.
import sys
import textwrap


def _visibility_cases():
    cases = []
    for n in range(15):
        cases.append([0] * n)
        cases.append(list(range(n)))
        cases.append(list(range(n, 0, -1)))
        cases.append([((i * 7) % 11) - 5 for i in range(n)])
        cases.append([i if i % 2 == 0 else -i for i in range(n)])
        cases.append([((i * i) % 7) / 3.0 - 1.0 for i in range(n)])
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

    results = []
    for series in payload["cases"]:
        graph = graphlib.visibility_graph(series)
        results.append(
            {
                "nodes": list(graph.nodes()),
                "edges": sorted(sorted(edge) for edge in graph.edges()),
                "values": [
                    [node, graph.nodes[node].get("value", "<missing>")]
                    for node in graph.nodes()
                ],
            }
        )

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
    return json.loads(proc.stdout)


def test_visibility_graph_matches_networkx_in_subprocesses():
    cases = _visibility_cases()
    assert len(cases) >= 50

    actual = _run_worker("franken_networkx", cases)
    expected = _run_worker("networkx", cases)

    assert actual == expected
