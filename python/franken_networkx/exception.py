"""FrankenNetworkX exception hierarchy — mirrors NetworkX exceptions for drop-in compatibility.

Re-exports every public exception class from ``networkx.exception`` under
the same name. Without this, code that does
``except franken_networkx.exception.NetworkXError`` (or imports the
class via this submodule path) breaks even though the same class is
reachable via the top-level ``franken_networkx.NetworkXError``.

The classes are exact aliases of their nx counterparts — fnx does not
define a parallel hierarchy — so isinstance/issubclass checks across
both libraries continue to work.
"""

from networkx.exception import (
    AmbiguousSolution,
    ExceededMaxIterations,
    HasACycle,
    NetworkXAlgorithmError,
    NetworkXError,
    NetworkXException,
    NetworkXNoCycle,
    NetworkXNoPath,
    NetworkXNotImplemented,
    NetworkXPointlessConcept,
    NetworkXUnbounded,
    NetworkXUnfeasible,
    NodeNotFound,
    PowerIterationFailedConvergence,
)

__all__ = [
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
