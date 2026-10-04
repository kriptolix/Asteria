"""Extensibility (spec section 17).

Allows registering renderers for specific elements without modifying the
parser. An ODT style can be mapped, via style_map, to a "tag" prefixed
with "custom:" (e.g. {"tag": "custom:note"}); when the renderer
encounters that prefix, it delegates to the function registered here
instead of generating a default HTML tag.

Example:

    from odt2web import register_renderer

    @register_renderer("custom:note")
    def render_note(node, context):
        return f"<div class='note'>...</div>"

    style_map = {"Warning": {"tag": "custom:note"}}
"""
from __future__ import annotations

from typing import Callable, Protocol


class RendererProtocol(Protocol):
    def __call__(self, node, context) -> str: ...


_REGISTRY: dict[str, RendererProtocol] = {}


def register_renderer(name: str) -> Callable[[RendererProtocol], RendererProtocol]:
    """Decorator that registers a global custom renderer under `name`
    (e.g. 'custom:note'). Can also be used as a regular function:
    register_renderer("custom:note")(my_function).
    """

    def decorator(func: RendererProtocol) -> RendererProtocol:
        _REGISTRY[name] = func
        return func

    return decorator


def unregister_renderer(name: str) -> None:
    _REGISTRY.pop(name, None)


def get_default_renderers() -> dict[str, RendererProtocol]:
    """Returns a copy of the global registry, used by default by
    convert()/convert_bytes() when the caller does not pass
    custom_renderers explicitly."""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """Useful in tests, to avoid leaking registrations across runs."""
    _REGISTRY.clear()
