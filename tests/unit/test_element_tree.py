"""Unit tests for pure SAP element tree normalization helpers."""

import pytest

from sap.element_tree import normalize_element_tree_payload


class TestNormalizeElementTreePayload:
    """Tests for pure element tree normalization."""

    def test_normalizes_nested_tree_to_canonical_flat_list(self) -> None:
        """Nested payloads should flatten to the Session element contract."""
        nested = {
            "id": "[/root]",
            "type": "GuiMainWindow",
            "name": "root",
            "text": "SAP",
            "x": 0,
            "y": 0,
            "width": 800,
            "height": 600,
            "visible": True,
            "enabled": True,
            "value": None,
            "children": [
                {
                    "id": "[/child]",
                    "type": "GuiButton",
                    "name": "save",
                    "text": "Save",
                    "x": 10,
                    "y": 20,
                    "width": 100,
                    "height": 24,
                    "visible": True,
                    "enabled": True,
                    "value": None,
                    "children": [],
                }
            ],
        }

        result = normalize_element_tree_payload(nested)

        assert len(result) == 2
        assert result[0]["element_id"] == "[/root]"
        assert result[0]["parent_id"] is None
        assert result[1]["element_id"] == "[/child]"
        assert result[1]["parent_id"] == "[/root]"

    def test_normalizes_flat_list_legacy_keys(self) -> None:
        """Already-flat payloads should also be canonicalized."""
        flat = [
            {
                "id": "[/root]",
                "type": "GuiMainWindow",
                "name": "root",
                "text": "SAP",
                "x": "1",
                "y": "2",
                "width": "800",
                "height": "600",
                "visible": 1,
                "enabled": 0,
                "value": None,
                "parent_id": None,
            }
        ]

        result = normalize_element_tree_payload(flat)

        assert result == [
            {
                "element_id": "[/root]",
                "element_type": "GuiMainWindow",
                "name": "root",
                "text": "SAP",
                "x": 1,
                "y": 2,
                "width": 800,
                "height": 600,
                "visible": True,
                "enabled": False,
                "value": None,
                "parent_id": None,
            }
        ]

    def test_rejects_non_dict_flat_items(self) -> None:
        """Flat payload validation should fail fast on malformed items."""
        with pytest.raises(TypeError, match="expected dict items"):
            normalize_element_tree_payload(["bad-item"])

    def test_honors_max_depth_for_nested_payloads(self) -> None:
        """Nested flattening should stop when the configured depth is exceeded."""
        nested = {
            "id": "[/l0]",
            "type": "GuiMainWindow",
            "name": "L0",
            "children": [
                {
                    "id": "[/l1]",
                    "type": "GuiUserArea",
                    "name": "L1",
                    "children": [
                        {
                            "id": "[/l2]",
                            "type": "GuiButton",
                            "name": "L2",
                            "children": [],
                        }
                    ],
                }
            ],
        }

        result = normalize_element_tree_payload(nested, max_depth=1)

        assert [element["element_id"] for element in result] == ["[/l0]", "[/l1]"]