"""Parity for non-algorithm ``franken_networkx`` child-module imports."""

from __future__ import annotations

import importlib
import pkgutil


_PACKAGE_NAMES = (
    "networkx.classes",
    "networkx.drawing",
    "networkx.generators",
    "networkx.linalg",
    "networkx.readwrite",
    "networkx.utils",
)


def _public_child_modules(package_name: str):
    package = importlib.import_module(package_name)
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
        parts = info.name.split(".")
        if any(part == "tests" or part.startswith("_") for part in parts):
            continue
        yield info.name


def test_non_algorithm_child_modules_import_like_networkx():
    failures = []
    for nx_name in sorted(
        name for package in _PACKAGE_NAMES for name in _public_child_modules(package)
    ):
        fnx_name = nx_name.replace("networkx.", "franken_networkx.", 1)
        try:
            importlib.import_module(nx_name)
            importlib.import_module(fnx_name)
        except Exception as exc:
            failures.append(
                (nx_name, fnx_name, type(exc).__name__, str(exc).splitlines()[0])
            )

    assert not failures


def test_classes_graph_child_module_aliases_networkx_module():
    actual = importlib.import_module("franken_networkx.classes.graph")
    expected = importlib.import_module("networkx.classes.graph")

    assert actual is expected


def test_generator_child_module_overlay_keeps_fnx_generator_result():
    generators = importlib.import_module("franken_networkx.generators.classic")
    graph = generators.path_graph(3)

    assert type(graph).__module__.startswith("franken_networkx")
