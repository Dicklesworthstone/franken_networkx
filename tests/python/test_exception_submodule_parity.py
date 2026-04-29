"""Parity test for the ``franken_networkx.exception`` submodule.

br-r37-c1-md9br: prior to the fix, ``python/franken_networkx/exception.py``
was an empty module — only the package docstring was present. Code that
did ``import franken_networkx.exception as e; raise e.NetworkXError(...)``
or ``except franken_networkx.exception.NetworkXNoPath`` broke even
though the same class was reachable via ``franken_networkx.NetworkXError``.

Lock the contract: every public exception class on
``networkx.exception`` must be importable from
``franken_networkx.exception`` and must be the *same* class object so
isinstance / except blocks work seamlessly across the two libraries.
"""

import networkx.exception as nx_exception
import franken_networkx.exception as fnx_exception


EXPECTED_CLASSES = [
    "AmbiguousSolution",
    "ExceededMaxIterations",
    "HasACycle",
    "NetworkXAlgorithmError",
    "NetworkXError",
    "NetworkXException",
    "NetworkXNoCycle",
    "NetworkXNoPath",
    "NetworkXNotImplemented",
    "NetworkXPointlessConcept",
    "NetworkXUnbounded",
    "NetworkXUnfeasible",
    "NodeNotFound",
    "PowerIterationFailedConvergence",
]


def test_every_nx_exception_class_is_reachable_via_fnx_exception_submodule():
    for name in EXPECTED_CLASSES:
        assert hasattr(fnx_exception, name), (
            f"franken_networkx.exception is missing {name!r} "
            f"(present on networkx.exception)"
        )


def test_fnx_exception_classes_identical_to_nx_exception_classes():
    """fnx must alias nx classes (not subclass them) so isinstance and
    except blocks across the two libraries match."""
    for name in EXPECTED_CLASSES:
        fnx_cls = getattr(fnx_exception, name)
        nx_cls = getattr(nx_exception, name)
        assert fnx_cls is nx_cls, (
            f"franken_networkx.exception.{name} is {fnx_cls}, expected the "
            f"same class object as networkx.exception.{name} ({nx_cls})"
        )


def test_fnx_exception_can_catch_real_fnx_raised_errors():
    """The exception-submodule classes must successfully catch errors
    raised by fnx public APIs (smoke check)."""
    import franken_networkx as fnx

    try:
        fnx.is_chordal(fnx.DiGraph())
    except fnx_exception.NetworkXNotImplemented as exc:
        assert "directed" in str(exc)
    else:
        raise AssertionError(
            "is_chordal on DiGraph should raise NetworkXNotImplemented"
        )


def test_fnx_exception_all_field_lists_every_expected_class():
    """``__all__`` should explicitly enumerate every re-exported class."""
    declared = set(getattr(fnx_exception, "__all__", ()))
    expected = set(EXPECTED_CLASSES)
    assert declared == expected, (
        f"franken_networkx.exception.__all__ mismatch: "
        f"missing={expected - declared}, extra={declared - expected}"
    )
