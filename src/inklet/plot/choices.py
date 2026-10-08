"""Keywords that take one of a few named values, checked where they are written.

A value the drawing code does not know used to fall through to a default --
`label_side="upside"` quietly put a rule's label below its line -- or to fail
only later, far from the call that wrote it. `choices` checks the value when
the method is called, and exposes `__option_check__(kwargs)` so a recipe
checks it when the call is recorded, as `paint_keywords` does for paint.
"""

from __future__ import annotations

import functools
from typing import Callable

__all__ = ["choices", "recorded"]


def choices(**allowed) -> Callable:
    """Check keyword options against the values each one accepts.

    `None` may be listed among the values; it is then the default and is not
    named in the error.
    """
    def decorate(func: Callable) -> Callable:
        title = func.__name__

        def check(kwargs) -> None:
            for name, values in allowed.items():
                if name not in kwargs or kwargs[name] in values:
                    continue
                listed = ", ".join(repr(v) for v in values if v is not None)
                raise ValueError(
                    f"{title}() {name}= must be one of {listed}, not {kwargs[name]!r}")

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            check(kwargs)
            return func(self, *args, **kwargs)

        wrapper.__option_check__ = check
        return wrapper
    return decorate


def recorded(check: Callable) -> Callable:
    """Run `check(arguments)` when a recipe records a call to the method.

    `arguments` maps each parameter name to the value the call binds to it,
    so a check can read `labels` whether it was passed by position or by
    keyword. Only what can be known from the call is checked here: the
    method itself still checks the same things when it draws.
    """
    def decorate(func: Callable) -> Callable:
        func.__record_check__ = check
        return func
    return decorate
