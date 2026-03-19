"""Pure helpers for normalizing SAP element tree payloads.

These helpers operate only on Python primitives returned by the COM worker.
They do not perform any QueueManager or COM access and can be reused by
session- and inspector-side code that needs a canonical flat element contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


NormalizedElement = Dict[str, Any]


def normalize_element_payload(element: Dict[str, Any]) -> NormalizedElement:
    """Normalize a single element dict to the canonical Session contract.

    Args:
        element: Raw element dictionary returned by the COM worker or tests.

    Returns:
        Canonical element dictionary using normalized key names and types.

    Raises:
        TypeError: If the payload is not a dict.
        ValueError: If scalar fields cannot be coerced to the expected type.
    """
    if not isinstance(element, dict):
        raise TypeError(
            "Element payload validation failed: expected dict, "
            f"got {type(element).__name__}."
        )

    return _normalize_element_dict(element)


def normalize_element_tree_payload(
    payload: Any,
    *,
    max_depth: int = 20,
    max_elements: int = 5000,
) -> List[NormalizedElement]:
    """Normalize an element tree payload into the canonical flat list contract.

    Args:
        payload: Nested element dict or already-flat list of element dicts.
        max_depth: Maximum recursion depth for nested payloads.
        max_elements: Maximum number of flattened elements for nested payloads.

    Returns:
        Canonical flat list of normalized element dictionaries.

    Raises:
        TypeError: If payload structure is malformed.
        ValueError: If scalar fields cannot be coerced to the expected type.
    """
    if isinstance(payload, list):
        return normalize_flat_element_list(payload)

    return flatten_nested_element_tree(
        payload,
        max_depth=max_depth,
        max_elements=max_elements,
    )


def normalize_flat_element_list(elements: List[Any]) -> List[NormalizedElement]:
    """Normalize an already-flat element list to the canonical Session contract.

    Args:
        elements: Flat list returned by a caller or test mock.

    Returns:
        Canonical flat list using normalized key names and types.

    Raises:
        TypeError: If any item in the list is not a dict.
        ValueError: If scalar fields cannot be coerced to the expected type.
    """
    normalized: List[NormalizedElement] = []

    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise TypeError(
                "Flat list validation failed: expected dict items, "
                f"got {type(element).__name__} at index {index}."
            )

        normalized.append(normalize_element_payload(element))

    return normalized


def flatten_nested_element_tree(
    root: Dict[str, Any],
    *,
    max_depth: int = 20,
    max_elements: int = 5000,
) -> List[NormalizedElement]:
    """Flatten a nested element tree into the canonical flat list contract.

    Args:
        root: Nested root element dictionary.
        max_depth: Maximum recursion depth.
        max_elements: Maximum number of flattened elements.

    Returns:
        Canonical flat list with parent back-references.

    Raises:
        TypeError: If the root or any child element is not a dict.
        ValueError: If scalar fields cannot be coerced to the expected type.
    """
    flattened: List[NormalizedElement] = []
    append_flattened_element_tree(
        root,
        flattened,
        max_depth=max_depth,
        max_elements=max_elements,
    )
    return flattened


def append_flattened_element_tree(
    elem: Dict[str, Any],
    result: List[NormalizedElement],
    *,
    parent_id: Optional[str] = None,
    current_depth: int = 0,
    max_depth: int = 20,
    max_elements: int = 5000,
) -> None:
    """Append a nested element tree to a flat result list.

    Args:
        elem: Current nested element dictionary.
        result: Output list accumulator.
        parent_id: Parent element ID for the current element.
        current_depth: Current recursion depth.
        max_depth: Maximum recursion depth.
        max_elements: Maximum number of flattened elements.

    Raises:
        TypeError: If the current element is not a dict.
        ValueError: If scalar fields cannot be coerced to the expected type.
    """
    if not isinstance(elem, dict):
        raise TypeError(
            f"append_flattened_element_tree expected dict, got {type(elem).__name__}."
        )

    if len(result) >= max_elements or current_depth > max_depth:
        return

    normalized_element = _normalize_element_dict(elem, parent_id=parent_id)
    result.append(normalized_element)

    children = elem.get("children", [])
    if not isinstance(children, list):
        return

    for child in children:
        if len(result) >= max_elements:
            break

        append_flattened_element_tree(
            child,
            result,
            parent_id=normalized_element["element_id"],
            current_depth=current_depth + 1,
            max_depth=max_depth,
            max_elements=max_elements,
        )


def _normalize_element_dict(
    raw_element: Dict[str, Any],
    *,
    parent_id: Optional[str] = None,
) -> NormalizedElement:
    """Convert a raw element dict into the canonical flat contract."""
    resolved_parent_id = raw_element.get("parent_id") if parent_id is None else parent_id

    return {
        "element_id": str(raw_element.get("element_id", raw_element.get("id", ""))),
        "element_type": str(
            raw_element.get("element_type", raw_element.get("type", "Unknown"))
        ),
        "name": str(raw_element.get("name", "")),
        "text": str(raw_element.get("text", "")),
        "x": int(raw_element.get("x", 0)),
        "y": int(raw_element.get("y", 0)),
        "width": int(raw_element.get("width", 0)),
        "height": int(raw_element.get("height", 0)),
        "visible": bool(raw_element.get("visible", True)),
        "enabled": bool(raw_element.get("enabled", True)),
        "value": raw_element.get("value", None),
        "parent_id": resolved_parent_id,
    }