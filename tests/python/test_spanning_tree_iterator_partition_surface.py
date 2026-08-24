"""Oracle coverage for spanning-tree iterator Partition records.

br-r37-c1-ozpfa
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_iterator_partition"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _partition_observations(partition_type, partition_value):
    same_weight = partition_type(1.0, {("other", "edge"): "excluded"})
    higher_weight = partition_type(2.0, {})
    copied = copy.copy(partition_value)
    return (
        repr(partition_value),
        partition_value == same_weight,
        partition_value < higher_weight,
        copied == partition_value,
        copied.partition_dict is partition_value.partition_dict,
        copied.partition_dict,
    )


def test_spanning_tree_iterator_partition_matches_legacy_oracle():
    nx = _legacy_networkx()
    legacy_partition_type = nx.SpanningTreeIterator.Partition
    partition_type = fnx.SpanningTreeIterator.Partition
    legacy_value = legacy_partition_type(1.0, {("a", "b"): "open"})
    value = partition_type(1.0, {("a", "b"): "open"})

    assert _partition_observations(partition_type, value) == _partition_observations(
        legacy_partition_type, legacy_value
    )


def test_arborescence_iterator_partition_matches_legacy_oracle():
    nx = _legacy_networkx()
    legacy_partition_type = nx.ArborescenceIterator.Partition
    partition_type = fnx.ArborescenceIterator.Partition
    legacy_value = legacy_partition_type(1.0, {("a", "b"): "open"})
    value = partition_type(1.0, {("a", "b"): "open"})

    assert _partition_observations(partition_type, value) == _partition_observations(
        legacy_partition_type, legacy_value
    )


def test_partition_types_are_exposed_by_all_legacy_aliases():
    assert fnx.algorithms.SpanningTreeIterator.Partition is fnx.SpanningTreeIterator.Partition
    assert (
        fnx.algorithms.tree.SpanningTreeIterator.Partition
        is fnx.SpanningTreeIterator.Partition
    )
    assert fnx.algorithms.ArborescenceIterator.Partition is fnx.ArborescenceIterator.Partition
    assert (
        fnx.algorithms.tree.ArborescenceIterator.Partition
        is fnx.ArborescenceIterator.Partition
    )
