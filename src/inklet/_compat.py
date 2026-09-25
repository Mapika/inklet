"""Deprecated spellings and import paths, kept working until Inklet 5.0.

Every Inklet deprecation goes through this module, so each one behaves the
same way: it raises `InkletDeprecationWarning`, a `DeprecationWarning`
subclass, whose message names the replacement, and the warning is attributed
to the line that used the old spelling rather than to Inklet's own code.

    moved_module(__name__, "inklet.volume")      # in an alias module
    renamed_keywords(colors="color")             # decorator: old= still works
    renamed_function("cluster_centres", cluster_centers)
    renamed_property("centre", "center")
    module_getattr(__name__, {"Harmonise": ("inklet.assets.Harmonize", Harmonize)})

The replacement is always the canonical name; internal callers use it, so the
test suite can turn this warning into an error without false alarms.
"""
from __future__ import annotations

import functools
import inspect
import sys
import warnings
from collections.abc import Callable, Mapping
from typing import Any

#: The release that removes everything deprecated through this module.
REMOVAL = "5.0"


class InkletDeprecationWarning(DeprecationWarning):
    """An Inklet 4.x name, keyword, import path or saved format that 5.0 removes.

    Filter on this class to silence or escalate Inklet's deprecations without
    affecting other libraries' `DeprecationWarning`s.
    """


def warn(message: str, stacklevel: int = 2) -> None:
    """Issue `message` as an `InkletDeprecationWarning`.

    `stacklevel` counts as `warnings.warn` counts it, from the caller of this
    function; import machinery frames are skipped by `warnings` itself, so a
    module-level call attributes the warning to the importing line.
    """
    warnings.warn(message, InkletDeprecationWarning, stacklevel=stacklevel + 1)


def moved_module(old: str, new: str, *, hint: str | None = None) -> None:
    """Warn that module `old` is an alias of `new`; call at alias module level."""
    message = (f"{old} is deprecated and will be removed in Inklet {REMOVAL}; "
               f"{hint or f'import from {new} instead'}.")
    # 1 = this function, 2 = the alias module body, 3 = the import statement.
    warn(message, stacklevel=3)


def removed_module(name: str, reason: str) -> None:
    """Warn that module `name` has no replacement and goes in 5.0."""
    warn(f"{name} is deprecated and will be removed in Inklet {REMOVAL}: {reason}",
         stacklevel=3)


class _Deprecated:
    """Default shown for a deprecated keyword in an exposed signature."""

    __slots__ = ("new",)

    def __init__(self, new: str) -> None:
        self.new = new

    def __repr__(self) -> str:
        return f"<deprecated: use {self.new}=>"


def renamed_keywords(**renames: str) -> Callable:
    """Decorator accepting old keyword names as warning aliases of new ones.

    `renamed_keywords(colors="color", centre="center")` lets callers keep
    writing `colors=` while the function is written against `color`. A call
    using the old name warns once per call site and passes its value on under
    the new name; giving both names is a `TypeError`.

    When the old name is still a real parameter of the function (a positional
    slot that released inventories record by name), the value is left under
    the old name for the function to reconcile with `resolve_renamed`, and
    only the warning is added.

    The exposed signature lists every old name not already present as a
    keyword-only parameter whose default reads `<deprecated: use new=>`, so
    `inspect.signature` still binds released calls.
    """
    def decorate(func: Callable) -> Callable:
        signature = inspect.signature(func)
        present = set(signature.parameters)
        title = func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if kwargs and not kwargs.keys().isdisjoint(renames):
                for old, new in renames.items():
                    if old not in kwargs:
                        continue
                    warn(f"{title}({old}=) is deprecated and will be removed in "
                         f"Inklet {REMOVAL}; use {new}= instead.", stacklevel=2)
                    if old in present:
                        continue
                    if new in kwargs:
                        raise TypeError(f"{title}() got both {new}= and its "
                                        f"deprecated spelling {old}=")
                    kwargs[new] = kwargs.pop(old)
            return func(*args, **kwargs)

        parameters = list(signature.parameters.values())
        extra = [inspect.Parameter(old, inspect.Parameter.KEYWORD_ONLY,
                                   default=_Deprecated(new))
                 for old, new in renames.items()
                 if old not in present and new in present]
        if extra:
            at = next((i for i, p in enumerate(parameters)
                       if p.kind is inspect.Parameter.VAR_KEYWORD), len(parameters))
            parameters[at:at] = extra
            wrapper.__signature__ = signature.replace(parameters=parameters)
        wrapper.__deprecated_keywords__ = dict(renames)
        return wrapper
    return decorate


def warn_renamed(func: Callable, kwargs: Mapping[str, Any], stacklevel: int = 2) -> None:
    """Warn now for old keywords in `kwargs` that `func` will accept later.

    For recorders that store a call and replay it on build: the warning should
    name the line that recorded the call, not the replay.
    """
    renames = getattr(func, "__deprecated_keywords__", {})
    for old, new in renames.items():
        if old in kwargs:
            warn(f"{func.__qualname__}({old}=) is deprecated and will be removed in "
                 f"Inklet {REMOVAL}; use {new}= instead.", stacklevel=stacklevel + 1)


def resolve_renamed(title: str, new: str, new_value: Any, old: str,
                    old_value: Any, default: Any = None) -> Any:
    """One value from a canonical parameter and the old one still in its slot.

    `None` means "not given" for both. Giving both is a `TypeError`.
    """
    if new_value is not None and old_value is not None:
        raise TypeError(f"{title}() got both {new}= and {old}=")
    if new_value is not None:
        return new_value
    return default if old_value is None else old_value


def renamed_function(old: str, new: Callable, *, owner: str | None = None) -> Callable:
    """A warning alias `old` of function `new`, with `new`'s signature."""
    target = f"{owner}.{new.__name__}" if owner else new.__name__

    @functools.wraps(new)
    def alias(*args: Any, **kwargs: Any) -> Any:
        warn(f"{old}() is deprecated and will be removed in Inklet {REMOVAL}; "
             f"use {target}() instead.", stacklevel=2)
        return new(*args, **kwargs)

    alias.__name__ = old
    alias.__qualname__ = old
    alias.__doc__ = f"Deprecated alias of `{target}`; removed in Inklet {REMOVAL}."
    return alias


def renamed_property(old: str, new: str) -> property:
    """A read-only warning alias `old` of attribute `new` on the same object."""
    def get(self: Any) -> Any:
        warn(f"{type(self).__name__}.{old} is deprecated and will be removed in "
             f"Inklet {REMOVAL}; use .{new} instead.", stacklevel=2)
        return getattr(self, new)

    get.__name__ = old
    return property(get, doc=f"Deprecated alias of `{new}`; removed in Inklet {REMOVAL}.")


def module_getattr(module: str, names: Mapping[str, tuple[str, Any]]) -> Callable:
    """A module `__getattr__` serving deprecated names.

    `names` maps each old name to `(new name, object)`. The object is returned
    as is, so `isinstance` and identity checks behave as with the new name.
    """
    def __getattr__(name: str) -> Any:
        try:
            new, value = names[name]
        except KeyError:
            raise AttributeError(f"module {module!r} has no attribute {name!r}") from None
        # `from package import Old` probes with hasattr() inside importlib
        # before fetching the name; warn only for the fetch, so once per use.
        if not sys._getframe(1).f_code.co_filename.startswith("<frozen importlib"):
            warn(f"{module}.{name} is deprecated and will be removed in Inklet "
                 f"{REMOVAL}; use {new} instead.", stacklevel=2)
        return value
    return __getattr__
