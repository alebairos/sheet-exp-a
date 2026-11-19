"""Function registry.

A function lands by adding its own module under ``src/functions/<group>/``::

    from src.functions import register

    @register("SUM")
    def sum_(*args):
        ...

``registry()`` imports every module of every group package found here, so no
shared list is ever edited.
"""

import importlib
import pkgutil

_REGISTRY = {}


def register(name):
    """Decorator: register ``fn`` under the (case-insensitive) function ``name``."""
    key = name.upper()

    def deco(fn):
        _REGISTRY[key] = fn
        return fn

    return deco


def _discover():
    for group in pkgutil.iter_modules(__path__):
        if not group.ispkg:
            continue
        pkg = importlib.import_module(f"{__name__}.{group.name}")
        for mod in pkgutil.iter_modules(pkg.__path__):
            importlib.import_module(f"{pkg.__name__}.{mod.name}")


def registry():
    """Return a ``{NAME: callable}`` dict of every registered function."""
    importlib.invalidate_caches()
    _discover()
    return dict(_REGISTRY)
