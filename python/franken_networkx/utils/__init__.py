"""Re-export of ``networkx.utils`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: prior to this stub, ``import franken_networkx.utils``
failed with ImportError even though ``franken_networkx.utils.X`` worked
via the package-level ``__getattr__`` fallback (used in
test_random_sequence_parity for ``fnx.utils.discrete_sequence``).

Star-imports the public surface from ``networkx.utils`` and falls
through to the source package for nested submodules
(``decorators``, ``misc``, ``random_sequence``, ``rcm``, ``union_find``,
``mapped_queue``, etc.) that the star-import doesn't auto-pull.
"""

from networkx.utils import *  # noqa: F401, F403


def __getattr__(name):
    import networkx.utils as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.utils as _src

    return sorted(set(globals()) | set(dir(_src)))
