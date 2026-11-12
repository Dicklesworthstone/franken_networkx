"""Drawing functions — thin delegation layer to NetworkX/matplotlib."""

from franken_networkx.drawing.nx_pylab import (
    display,
    draw,
    draw_bipartite,
    draw_circular,
    draw_forceatlas2,
    draw_kamada_kawai,
    draw_networkx,
    draw_networkx_edge_labels,
    draw_networkx_edges,
    draw_networkx_labels,
    draw_networkx_nodes,
    draw_planar,
    draw_random,
    draw_shell,
    draw_spectral,
    draw_spring,
    to_latex,
    to_latex_raw,
    write_latex,
)
from franken_networkx.drawing.layout import (
    arf_layout,
    bfs_layout,
    bipartite_layout,
    circular_layout,
    forceatlas2_layout,
    fruchterman_reingold_layout,
    kamada_kawai_layout,
    multipartite_layout,
    planar_layout,
    random_layout,
    rescale_layout_dict,
    shell_layout,
    spiral_layout,
    spectral_layout,
    spring_layout,
)

__all__ = [
    "draw",
    "display",
    "draw_bipartite",
    "draw_circular",
    "draw_forceatlas2",
    "draw_kamada_kawai",
    "draw_networkx",
    "draw_networkx_edge_labels",
    "draw_networkx_edges",
    "draw_networkx_labels",
    "draw_networkx_nodes",
    "draw_planar",
    "draw_random",
    "draw_shell",
    "draw_spectral",
    "draw_spring",
    "to_latex",
    "to_latex_raw",
    "write_latex",
    "arf_layout",
    "bfs_layout",
    "bipartite_layout",
    "circular_layout",
    "forceatlas2_layout",
    "fruchterman_reingold_layout",
    "kamada_kawai_layout",
    "multipartite_layout",
    "planar_layout",
    "random_layout",
    "rescale_layout_dict",
    "shell_layout",
    "spiral_layout",
    "spectral_layout",
    "spring_layout",
]


# br-r37-c1-yze40: networkx.drawing re-exports apply_matplotlib_colors
# (from nx_pylab) and rescale_layout (from layout) into its namespace via
# star-imports, so ``nx.drawing.apply_matplotlib_colors`` and
# ``nx.drawing.rescale_layout`` resolve.  fnx keeps both public wrappers in
# the top-level package, so mirror them here for ``nx.drawing.<name>``
# parity — and as the *same* objects, since nx itself has
# ``nx.drawing.rescale_layout is nx.rescale_layout``.  The parent package
# binds both names (def lines ~17740 / ~34526) well before it imports this
# subpackage (~36769), so the lookup into the partially-initialised parent
# is safe.
from franken_networkx import (  # noqa: E402
    apply_matplotlib_colors,
    rescale_layout,
)

__all__ += ["apply_matplotlib_colors", "rescale_layout"]


def _install_drawing_child_aliases():
    """br-r37-c1-ibcok: also put the child modules on ``__all__``.

    ``networkx.drawing`` declares no ``__all__``, so ``from networkx.drawing
    import *`` binds every public module-level name — which INCLUDES its five
    child modules (``layout``, ``nx_agraph``, ``nx_latex``, ``nx_pydot``,
    ``nx_pylab``). fnx declares an explicit ``__all__``, so those names were
    silently dropped from the star-import surface even though the modules
    themselves resolve fine as attributes. Collect the names here rather than
    hard-coding them, so the export surface follows whatever children the
    installed NetworkX actually has.
    """
    import importlib
    import pkgutil
    import sys
    import networkx.drawing as _src

    native_children = {"layout", "nx_pylab"}
    exported = set(native_children)
    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        exported.add(name)
        if name in native_children:
            continue
        alias = f"{__name__}.{name}"
        if alias in sys.modules:
            continue
        module = importlib.import_module(f"networkx.drawing.{name}")
        sys.modules[alias] = module
        globals()[name] = module

    __all__.extend(sorted(exported - set(__all__)))


_install_drawing_child_aliases()
