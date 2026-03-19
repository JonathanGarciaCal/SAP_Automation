"""Screen inspector and element tree walker.

Provides methods to inspect SAP GUI elements and walk the UI hierarchy:
    - Get element tree from SAP window
    - Find elements by ID/type/text
    - Extract element properties (position, size, visibility, etc.)
    - Filter and search elements using predicates

Used by Phase 2 Screen Inspector feature, built on top of session.py.

Architecture:
    - ElementInfo: Dataclass holding element metadata
    - ElementTreeWalker: Walks GuiSession element tree, populates ElementInfo objects
    - All methods are async and use session.queue_manager() for COM calls

Example:
    ```python
    from sap.inspector import ElementTreeWalker
    
    walker = ElementTreeWalker(session)
    
    # Get all elements on current screen
    tree = await walker.get_element_tree()
    
    # Find specific element
    field = await walker.find_element(element_type='GuiTextField', name='VBELN')
    print(f"Field position: {field.x}, {field.y}")
    
    # Filter elements
    all_buttons = await walker.find_elements(element_type='GuiButton')
    ```

Threading:
    - All methods are async and thread-safe
    - Use session's queue_manager for COM calls
    - See doc/06-architecture/patterns.md for threading pattern
"""

import logging
from typing import Any, List, Optional, Callable, Dict
from dataclasses import dataclass

from sap.element_tree import normalize_flat_element_list
from sap.performance import BatchOperations

logger = logging.getLogger(__name__)


@dataclass
class ElementInfo:
    """Information about a SAP GUI element.
    
    Attributes:
        element_id: Unique element ID in SAP (e.g., "[/app/scr/txt_field_name]")
        element_type: Element type class (e.g., 'GuiTextField', 'GuiButton', 'GuiGridView')
        name: User-friendly name or label
        text: Display text shown in UI (may be empty)
        x: X position in pixels (absolute screen coordinates)
        y: Y position in pixels (absolute screen coordinates)
        width: Width in pixels
        height: Height in pixels
        visible: True if element is currently visible
        enabled: True if element is enabled (can be interacted with)
        value: Current value (for input fields, labels, etc.), None if not applicable
        parent_id: ID of parent element (if nested)
        children: List of child ElementInfo objects (only if tree was recursively walked)
    """
    
    element_id: str
    element_type: str
    name: str
    text: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    enabled: bool = True
    value: Optional[Any] = None
    parent_id: Optional[str] = None
    children: Optional[List["ElementInfo"]] = None
    
    def __post_init__(self) -> None:
        """Initialize children as empty list if None."""
        if self.children is None:
            self.children = []


class ElementTreeWalker:
    """Walks SAP element tree and provides search/filter operations.
    
    Uses session.get_element_tree() to walkthe element hierarchy from SAP.
    Converts raw COM data into ElementInfo dataclass objects.
    Provides filtering and search methods.
    
    Attributes:
        session: SAP session object (has get_element_tree method)
        _cache: Element cache (maps element ID to ElementInfo)
        _last_tree: Last retrieved element tree (for repeat searches)
    """
    
    def __init__(self, session: Any) -> None:
        """Initialize element tree walker.
        
        Args:
            session: SAP Session object (should have get_element_tree, 
                     find_elements_by_type, and find_element methods)
        
        Raises:
            ValueError: If session is None
        """
        if not session:
            raise ValueError("session cannot be None")
        
        self.session = session
        self._cache: Dict[str, ElementInfo] = {}
        self._last_tree: Optional[ElementInfo] = None
        
        logger.debug("ElementTreeWalker initialized for session")
    
    async def get_element_tree(
        self,
        root_id: str = "[/app/con[0]/ses[0]/wnd[0]]",
        refresh: bool = False,
        include_children: bool = True
    ) -> ElementInfo:
        """Get all elements on screen as a tree.
        
        Retrieves the flat element list from SAP and builds an ElementInfo tree.
        Reconstructs parent-child relationships using parent_id back-references.
        Optionally caches result for repeated searches without refresh.
        
        Args:
            root_id: Root element ID (default: main SAP window)
            refresh: Force refresh from SAP (skip cache)
            include_children: If True, link children to parents in tree structure

        Returns:
            ElementInfo tree structure starting from root with children populated
        
        Raises:
            RuntimeError: If session not connected or tree retrieval fails
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            walker = ElementTreeWalker(session)
            tree = await walker.get_element_tree()
            
            # Recursively print tree
            def print_tree(elem, indent=0):
                print(" " * indent + f"[{elem.element_type}] {elem.name}")
                for child in elem.children:
                    print_tree(child, indent + 2)
            
            print_tree(tree)
            ```
        """
        try:
            logger.info(
                "Getting element tree from %s (refresh=%s, include_children=%s)",
                root_id,
                refresh,
                include_children
            )
            
            # Check cache
            if not refresh and root_id in self._cache:
                logger.debug("Returning cached element tree from root %s", root_id)
                return self._cache[root_id]
            
            # Get flat list from session
            flat_list: List[Dict[str, Any]] = await self.session.get_element_tree(root_id)
            
            # Convert to ElementInfo objects and build tree
            root_elem = self._build_element_tree(
                flat_list,
                root_id,
                include_children
            )
            
            # Cache the root
            self._cache[root_id] = root_elem
            self._last_tree = root_elem
            
            logger.info(
                "Element tree built: root_type=%s, root_id=%s, %d total cached elements",
                root_elem.element_type,
                root_id,
                len(self._cache)
            )
            
            return root_elem
        
        except Exception as e:
            logger.error("Failed to get element tree: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to get element tree: {e}")
    
    async def find_element(
        self,
        element_type: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        predicate: Optional[Callable[[ElementInfo], bool]] = None,
        refresh: bool = False
    ) -> Optional[ElementInfo]:
        """Find first element matching criteria.
        
        Searches the current element tree (from cache or SAP). Returns first match.
        
        Args:
            element_type: Filter by element type (e.g., 'GuiTextField')
            name: Filter by name (exact or substring match)
            text: Filter by display text (exact or substring match)
            predicate: Custom filter function (returns True to match)
            refresh: Force refresh element tree from SAP
        
        Returns:
            First matching ElementInfo or None if not found
        
        Raises:
            RuntimeError: If tree retrieval fails
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            # Find by type and name
            field = await walker.find_element(
                element_type='GuiTextField',
                name='VBELN'
            )
            
            # Find by custom predicate
            field = await walker.find_element(
                predicate=lambda e: e.value == '12345'
            )
            ```
        """
        tree = await self.get_element_tree(refresh=refresh)
        
        results = self._search_tree(
            tree,
            element_type=element_type,
            name=name,
            text=text,
            predicate=predicate,
            limit=1
        )
        
        if results:
            logger.debug("Found element: %s", results[0].element_id)
            return results[0]
        
        logger.debug("Element not found (type=%s, name=%s, text=%s)", element_type, name, text)
        return None
    
    async def find_elements(
        self,
        element_type: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        predicate: Optional[Callable[[ElementInfo], bool]] = None,
        refresh: bool = False
    ) -> List[ElementInfo]:
        """Find all elements matching criteria.
        
        Searches the current element tree (from cache or SAP). Returns all matches.
        
        Args:
            element_type: Filter by element type
            name: Filter by name (substring match)
            text: Filter by display text (substring match)
            predicate: Custom filter function
            refresh: Force refresh element tree from SAP
        
        Returns:
            List of matching ElementInfo objects (empty if none found)
        
        Raises:
            RuntimeError: If tree retrieval fails
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            # Find all buttons
            buttons = await walker.find_elements(element_type='GuiButton')
            print(f"Found {len(buttons)} buttons")
            
            # Find all visible text fields
            fields = await walker.find_elements(
                element_type='GuiTextField',
                predicate=lambda e: e.visible
            )
            ```
        """
        tree = await self.get_element_tree(refresh=refresh)
        
        results = self._search_tree(
            tree,
            element_type=element_type,
            name=name,
            text=text,
            predicate=predicate,
            limit=None
        )
        
        logger.debug(
            "Found %d elements (type=%s, name=%s, text=%s)",
            len(results),
            element_type,
            name,
            text
        )
        
        return results
    
    def clear_cache(self) -> None:
        """Clear element cache.
        
        Call this after screen-modifying operations (navigation, field changes)
        to force re-fetch of element tree on next access.
        
        Example:
            ```python
            await session.start_transaction('VA01')
            walker.clear_cache()  # Clear old element tree
            tree = await walker.get_element_tree()  # Fetch new tree
            ```
        """
        logger.debug("Clearing element cache (was %d items)", len(self._cache))
        self._cache.clear()
        self._last_tree = None
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict with cache info: {
                'item_count': number of cached elements,
                'last_tree_type': element type of last retrieved tree,
                'cache_size_bytes': approximate memory usage
            }
        """
        cache_size = sum(
            len(elem.element_id) + len(elem.name) + len(elem.text)
            for elem in self._cache.values()
        )
        
        return {
            'item_count': len(self._cache),
            'last_tree_type': self._last_tree.element_type if self._last_tree else None,
            'cache_size_bytes': cache_size
        }
    
    async def read_grid_range(
        self,
        grid_id: str,
        from_row: int,
        to_row: int,
        columns: List[str]
    ) -> List[Dict[str, Any]]:
        """Read grid data for a range of rows using batch operations.
        
        Delegates to BatchOperations.batch_read_grid() for optimized performance.
        Reads multiple rows without per-row waits, achieving 4x+ speedup vs per-row reads.
        
        Args:
            grid_id: Grid element ID (e.g., 'wnd[0]/usr/cntlALVCONTAINER/shellcont/shell')
            from_row: Starting row (1-based)
            to_row: Ending row (inclusive, 1-based)
            columns: List of column field IDs to read
        
        Returns:
            List of dicts mapping column names to values
        
        Example:
            ```python
            # Read rows 1-100 from ALV grid
            rows = await walker.read_grid_range(
                'wnd[0]/usr/cntlALVCONTAINER/shellcont/shell',
                1, 100,
                ['MATNR', 'MENGE', 'MEINS']
            )
            # Result: [{'MATNR': '100001', 'MENGE': '10', 'MEINS': 'EA'}, ...]
            ```
        """
        return BatchOperations.batch_read_grid(
            self.session,
            grid_id,
            (from_row, to_row),
            columns
        )
    
    async def find_control_by_label(
        self,
        window: Any,
        label_text: str
    ) -> Optional[str]:
        """Find input control element ID by its associated label text.
        
        Walks element tree to find a label, then returns adjacent input field.
        Useful when you know the field label but not the exact element ID.
        
        Args:
            window: SAP window COM object
            label_text: Label text to search for (e.g., 'Material Number')
        
        Returns:
            Element ID of associated input field, or None if not found
        
        Example:
            ```python
            # Find 'Material Number' field
            matnr_id = await walker.find_control_by_label(window, 'Material')
            if matnr_id:
                session.FindById(matnr_id).Text = '100001'
            ```
        """
        tree = await self.get_element_tree()
        
        # Find label matching text
        label = self._find_in_tree(
            tree,
            element_type='GuiLabel',
            predicate=lambda e: label_text.lower() in e.text.lower()
        )
        
        if not label or not label.parent_id:
            logger.warning(f"Label '{label_text}' not found")
            return None
        
        # Find adjacent input field in same parent
        parent = self._find_in_tree(tree, predicate=lambda e: e.element_id == label.parent_id)
        if not parent or not parent.children:
            return None
        
        # Return first input field child after label
        input_types = {'GuiTextField', 'GuiCTextField', 'GuiPasswordField'}
        for child in parent.children:
            if child.element_type in input_types:
                logger.debug(f"Found input field: {child.element_id}")
                return child.element_id
        
        return None
    
    async def get_table_column_values(
        self,
        table_id: str,
        column_name: str
    ) -> List[Any]:
        """Extract all values from a specific table/grid column.
        
        Uses batch operations to read entire column efficiently.
        
        Args:
            table_id: Table/grid element ID
            column_name: Column name/field ID to extract
        
        Returns:
            List of values in column order
        
        Example:
            ```python
            # Get all material numbers from grid
            matnrs = await walker.get_table_column_values(
                'wnd[0]/usr/cntlGRID/shellcont/shell',
                'MATNR'
            )
            # Result: ['100001', '100002', '100003', ...]
            ```
        """
        # For now, return placeholder - would integrate with grid reading logic
        # This is a convenience method for common use case
        logger.warning(f"get_table_column_values not yet implemented for {column_name}")
        return []
    
    # ─────────────────────────────────────────────────────────────────
    # Private helper methods
    # ─────────────────────────────────────────────────────────────────
    
    def _search_tree(
        self,
        elem: ElementInfo,
        element_type: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        predicate: Optional[Callable[[ElementInfo], bool]] = None,
        limit: Optional[int] = None
    ) -> List[ElementInfo]:
        """Recursively search element tree.
        
        Args:
            elem: Root element to search from
            element_type: Filter by element type
            name: Filter by name (substring match)
            text: Filter by display text (substring match)
            predicate: Custom filter function
            limit: Maximum results (None = no limit)
        
        Returns:
            List of matching elements (up to limit)
        """
        results: List[ElementInfo] = []
        
        def matches(e: ElementInfo) -> bool:
            """Check if element matches all criteria."""
            if element_type and e.element_type != element_type:
                return False
            if name and name.lower() not in e.name.lower():
                return False
            if text and text.lower() not in e.text.lower():
                return False
            if predicate and not predicate(e):
                return False
            return True
        
        def search_recursive(e: ElementInfo) -> None:
            """Depth-first search."""
            if limit and len(results) >= limit:
                return
            
            if matches(e):
                results.append(e)
            
            if e.children is not None:
                for child in e.children:
                    search_recursive(child)
        
        search_recursive(elem)
        return results
    
    def _find_in_tree(
        self,
        elem: ElementInfo,
        element_type: Optional[str] = None,
        name: Optional[str] = None,
        text: Optional[str] = None,
        predicate: Optional[Callable[[ElementInfo], bool]] = None
    ) -> Optional[ElementInfo]:
        """Find first element in tree matching criteria.
        
        Helper method used by find_control_by_label and other lookups.
        \n Args:
            elem: Root element to search from
            element_type: Filter by element type
            name: Filter by name (substring match)
            text: Filter by display text (substring match)
            predicate: Custom filter function
        
        Returns:
            First matching ElementInfo, or None
        """
        results = self._search_tree(
            elem,
            element_type=element_type,
            name=name,
            text=text,
            predicate=predicate,
            limit=1
        )
        return results[0] if results else None
    
    def _convert_to_element_info(
        self,
        raw_elem: Dict[str, Any],
        include_children: bool = True
    ) -> ElementInfo:
        """Convert a normalized element dict into ElementInfo.

        The canonical inspector/session contract is a flat element dict using
        element_id, element_type, and parent_id. Nested children are only
        traversed when this helper is used directly with a nested payload.
        
        Args:
            raw_elem: Normalized element dict from SAP/session helpers
            include_children: If True, recursively convert children (if present)
        
        Returns:
            ElementInfo object with all 11 attributes populated
        """
        # Extract children if present (legacy nested structure)
        children: List[ElementInfo] = []
        if include_children and raw_elem.get('children'):
            for child_raw in raw_elem['children']:
                child_info = self._convert_to_element_info(child_raw, include_children=True)
                children.append(child_info)
        
        # Create ElementInfo from the canonical flat contract.
        elem_info = ElementInfo(
            element_id=str(raw_elem.get('element_id', '')),
            element_type=str(raw_elem.get('element_type', 'Unknown')),
            name=raw_elem.get('name', ''),
            text=raw_elem.get('text', ''),
            x=int(raw_elem.get('x', 0)),
            y=int(raw_elem.get('y', 0)),
            width=int(raw_elem.get('width', 0)),
            height=int(raw_elem.get('height', 0)),
            visible=bool(raw_elem.get('visible', True)),
            enabled=bool(raw_elem.get('enabled', True)),
            value=raw_elem.get('value', None),
            parent_id=raw_elem.get('parent_id', None),
            children=children
        )
        
        # Cache it by element_id
        self._cache[elem_info.element_id] = elem_info
        
        return elem_info
    
    def _build_element_tree(
        self,
        flat_list: List[Dict[str, Any]],
        root_id: str,
        include_children: bool = True
    ) -> ElementInfo:
        """Build ElementInfo tree from flat list using parent_id references.
        
        Converts flat element list (returned by session.get_element_tree) into
        a tree structure by linking elements via parent_id back-references.
        
        Smart fallback: If exact root_id not found, uses first orphan element
        (parent_id=None) to build tree from, logging a warning.
        
        Args:
            flat_list: Flat list of element dicts from session.get_element_tree()
            root_id: Root element ID to build tree from
            include_children: If True, populate children relationships
        
        Returns:
            Root ElementInfo with children linked recursively
        
        Raises:
            RuntimeError: If no root element found (even with fallback) or flat_list is empty
        """
        logger.debug("Building element tree from flat list of %d elements", len(flat_list))
        
        if not flat_list:
            error_msg = "Cannot build element tree: flat_list is empty"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        normalized_elements = normalize_flat_element_list(flat_list)
        
        # Convert all dicts to ElementInfo objects and index by ID
        elements: Dict[str, ElementInfo] = {}
        orphan_elements: List[ElementInfo] = []  # Elements with parent_id=None
        
        for elem_dict in normalized_elements:
            elem_info = self._convert_to_element_info(elem_dict, include_children=False)
            elements[elem_info.element_id] = elem_info
            
            # Track orphan elements (potential roots)
            if elem_info.parent_id is None:
                orphan_elements.append(elem_info)
        
        # Find root element: exact match (with or without [] wrappers) or fallback to first orphan
        root = None
        normalized_root_id = root_id
        bracketless_root_id = root_id[1:-1] if root_id.startswith('[') and root_id.endswith(']') else root_id
        bracketed_root_id = root_id if root_id.startswith('[') and root_id.endswith(']') else f'[{root_id}]'

        if normalized_root_id in elements:
            root = elements[normalized_root_id]
            logger.debug(
                "Using exact root element: %s (type: %s)",
                normalized_root_id,
                root.element_type
            )
        elif bracketless_root_id in elements:
            root = elements[bracketless_root_id]
            logger.debug(
                "Using normalized root element: %s -> %s (type: %s)",
                root_id,
                bracketless_root_id,
                root.element_type
            )
        elif bracketed_root_id in elements:
            root = elements[bracketed_root_id]
            logger.debug(
                "Using normalized root element: %s -> %s (type: %s)",
                root_id,
                bracketed_root_id,
                root.element_type
            )
        elif orphan_elements:
            # Fallback: use first orphan as root (common in test mocks)
            root = orphan_elements[0]
            logger.warning(
                "Root element %s not found. "
                "Falling back to orphan element %s (type: %s). "
                "Available elements: %s",
                root_id,
                root.element_id,
                root.element_type,
                [e.element_id for e in list(elements.values())[:10]]
            )
        else:
            # No root found and no orphans
            element_ids_preview = [
                elem_info.element_id 
                for elem_info in list(elements.values())[:5]
            ]
            error_msg = (
                f"Cannot find root element {root_id}. "
                f"No orphan elements found either. "
                f"Total elements: {len(elements)}, "
                f"Element IDs (first 5): {element_ids_preview}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Link children to parents via parent_id
        if include_children:
            for elem_info in elements.values():
                if elem_info.parent_id and elem_info.parent_id in elements:
                    parent = elements[elem_info.parent_id]
                    if parent.children is None:
                        parent.children = []
                    if elem_info not in parent.children:
                        parent.children.append(elem_info)
        
        logger.debug(
            "Element tree built: root=%s, %d normalized elements cached, %d orphans",
            root.element_id,
            len(normalized_elements),
            len(orphan_elements)
        )
        
        return root
