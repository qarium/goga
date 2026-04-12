from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from goga.codemanifest.errors import ManifestParseError
from goga.codemanifest.nodes import (
    AnnotationsNode,
    BodyNode,
    DocumentRoot,
    EntityTypeNode,
    FooterNode,
    HeaderNode,
    ImportItemNode,
    ImportsNode,
    MethodNode,
    PropertyNode,
    RoutineTypeNode,
    UsageItemNode,
    UsagesNode,
)

_VALID_HEADER_KEYS = frozenset({"Imports", "Usages", "Annotations"})
_VALID_FOOTER_KEYS = frozenset({"Author", "CreatedAt", "Description"})


class Factory:
    """Parses a CODEMANIFEST YAML file and builds a DocumentRoot tree."""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def create(self, parent: Optional[DocumentRoot] = None) -> DocumentRoot:
        """Load and parse the CODEMANIFEST file, returning a DocumentRoot tree."""
        filepath = Path(self._path) / "CODEMANIFEST"

        with filepath.open(encoding="utf-8") as fh:
            raw = fh.read()

        documents = list(yaml.safe_load_all(raw))

        _num_sections = 3  # header, body, footer
        header_data = documents[0] if len(documents) > 0 and documents[0] else {}
        body_data = documents[1] if len(documents) > 1 and documents[1] else {}
        footer_data = documents[_num_sections - 1] if len(documents) >= _num_sections and documents[2] else {}

        if not isinstance(header_data, dict):
            header_data = {}
        if not isinstance(body_data, dict):
            body_data = {}
        if not isinstance(footer_data, dict):
            footer_data = {}

        header = self._parse_header(header_data, str(filepath))
        body, embedded_entities, embedded_routines = self._parse_body(body_data)
        footer = self._parse_footer(footer_data, str(filepath))

        # Build embeddings list by matching embedded type names with import source paths
        # Unmatched embedded types (no matching import) are added directly to body
        embeddings, unmatched_entities, unmatched_routines = self._build_embeddings(
            header.imports.items, embedded_entities, embedded_routines
        )
        body.entities.extend(unmatched_entities)
        body.routines.extend(unmatched_routines)

        document_root = DocumentRoot(
            parent=parent,
            path=self._path,
            header=header,
            body=body,
            footer=footer,
            embeddings=embeddings,
        )

        self._wire_references(document_root, header, body, footer)

        # Populate types dict: map type names to their nodes
        document_root.types = self._build_types_dict(body)

        # Populate links dict: collect all link references from annotations
        document_root.links = self._collect_links(document_root)

        return document_root

    @staticmethod
    def _wire_references(
        document_root: DocumentRoot,
        header: HeaderNode,
        body: BodyNode,
        footer: FooterNode,
    ) -> None:
        """Wire root and parent references for all document nodes."""
        header.root = document_root
        header.parent = document_root
        header.imports.root = document_root
        header.imports.parent = header
        for item in header.imports.items:
            item.root = document_root
            item.parent = header.imports
        header.usages.root = document_root
        header.usages.parent = header
        for item in header.usages.items:
            item.root = document_root
            item.parent = header.usages
            item.annotations.root = document_root
            item.annotations.parent = item
        header.annotations.root = document_root
        header.annotations.parent = header

        body.root = document_root
        body.parent = document_root
        for entity in body.entities:
            entity.root = document_root
            entity.parent = body
            entity.annotations.root = document_root
            entity.annotations.parent = entity
            for prop in entity.properties:
                prop.root = document_root
                prop.parent = entity
                prop.annotations.root = document_root
                prop.annotations.parent = prop
            for method in entity.methods:
                method.root = document_root
                method.parent = entity
                method.annotations.root = document_root
                method.annotations.parent = method
        for routine in body.routines:
            routine.root = document_root
            routine.parent = body
            routine.annotations.root = document_root
            routine.annotations.parent = routine

        footer.root = document_root
        footer.parent = document_root

    def _parse_header(self, data: dict, filepath: str) -> HeaderNode:
        """Parse the header section (Section 1) of the CODEMANIFEST."""
        unknown_keys = set(data.keys()) - _VALID_HEADER_KEYS
        if unknown_keys:
            sorted_keys = ", ".join(sorted(unknown_keys))
            raise ManifestParseError(
                f"Unknown keys in header: {sorted_keys}",
                filepath,
            )

        imports_node = self._parse_imports(data.get("Imports"), filepath)
        usages_node = self._parse_usages(data.get("Usages"))
        annotations_text = data.get("Annotations", "")
        if annotations_text is None:
            annotations_text = ""
        annotations_text = str(annotations_text)
        annotations_node = AnnotationsNode(text=annotations_text, links=self._extract_links(annotations_text))

        # Collect imported type names
        types: list[str] = []
        for item in imports_node.items:
            types.extend(item.type_name)

        return HeaderNode(
            imports=imports_node,
            usages=usages_node,
            annotations=annotations_node,
            types=types,
            data=dict(data),
        )

    def _parse_imports(self, data: object, filepath: str) -> ImportsNode:
        """Parse the Imports section of the header."""
        items: list[ImportItemNode] = []

        if data is None:
            return ImportsNode(items=items)

        if not isinstance(data, list):
            raise ManifestParseError(
                "Imports must be a list",
                filepath,
            )

        for entry in data:
            if not isinstance(entry, dict):
                continue

            from_path = entry.get("From", "")
            types_list = entry.get("Types", [])

            if not isinstance(types_list, list):
                continue

            for type_entry in types_list:
                type_str = str(type_entry)
                # Check for AS alias (case-sensitive, must be uppercase)
                if " AS " in type_str:
                    parts = type_str.split(" AS ", 1)
                    type_name = parts[0].strip()
                    alias = parts[1].strip()
                else:
                    type_name = type_str.strip()
                    alias = ""

                items.append(
                    ImportItemNode(
                        type_name={type_name},
                        from_path=str(from_path),
                        alias=alias,
                        data=dict(entry),
                    )
                )

        return ImportsNode(items=items)

    def _parse_usages(self, data: object) -> UsagesNode:
        """Parse the Usages section of the header."""
        items: list[UsageItemNode] = []

        if data is None:
            return UsagesNode(items=items)

        if not isinstance(data, dict):
            return UsagesNode(items=items)

        for name, value in data.items():
            value_str = str(value) if value is not None else ""
            annotations = self._build_usage_annotations(value_str)
            items.append(
                UsageItemNode(
                    name=str(name),
                    annotations=annotations,
                    data={str(name): value},
                )
            )

        return UsagesNode(items=items)

    def _build_usage_annotations(self, value: str) -> AnnotationsNode:
        """Build an AnnotationsNode for a usage entry based on its value type."""
        if value.startswith("http://") or value.startswith("https://"):
            return AnnotationsNode(url=value, links=self._extract_links(value))
        if value.endswith(".md"):
            return AnnotationsNode(filepath=value, links=self._extract_links(value))
        return AnnotationsNode(text=value, links=self._extract_links(value))

    def _parse_body(
        self, data: dict
    ) -> tuple[BodyNode, list[tuple[str, bool, str, dict]], list[tuple[str, bool, str, str, dict]]]:
        """Parse the body section (Section 2) of the CODEMANIFEST.

        Returns a tuple of:
        - BodyNode with non-embedded entities and routines
        - List of embedded entity info: (name, embedded_flag, key, value_dict)
        - List of embedded routine info: (name, embedded_flag, signature, data_dict_or_text, data_dict)
        """
        entities: list[EntityTypeNode] = []
        routines: list[RoutineTypeNode] = []
        embedded_entities: list[tuple[str, bool, str, dict]] = []
        embedded_routines: list[tuple[str, bool, str, str, dict]] = []

        for signature_key, value in data.items():
            key = str(signature_key)

            if isinstance(value, str):
                # Plain string value -> RoutineTypeNode
                name, signature = self._split_name_and_signature(key)
                name, is_embedded = self._strip_embedded_prefix(name)
                value_text = str(value)
                if is_embedded:
                    embedded_routines.append((name, True, signature, value_text, {key: value}))
                else:
                    routines.append(
                        RoutineTypeNode(
                            name=name,
                            signature=signature,
                            embedded=False,
                            annotations=AnnotationsNode(text=value_text, links=self._extract_links(value_text)),
                            data={key: value},
                        )
                    )
            elif isinstance(value, dict):
                has_properties = "properties" in value
                has_methods = "methods" in value
                has_mutations_in_sig = "::" in key.split("(", maxsplit=1)[0]
                has_embedded_prefix = key.startswith("->")

                if has_properties or has_methods or has_mutations_in_sig or has_embedded_prefix:
                    # EntityTypeNode
                    entity = self._parse_entity(key, value)
                    if entity.embedded:
                        embedded_entities.append((entity.name, True, key, dict(value)))
                    else:
                        entities.append(entity)
                else:
                    # RoutineTypeNode from dict (has location/annotations but no entity features)
                    name, signature = self._split_name_and_signature(key)
                    name, is_embedded = self._strip_embedded_prefix(name)
                    location = self._resolve_location(value.get("location", ""))
                    annotations_text = value.get("annotations", "")
                    if annotations_text is None:
                        annotations_text = ""
                    annotations_text = str(annotations_text)
                    if is_embedded:
                        embedded_routines.append((name, True, signature, annotations_text, dict(value)))
                    else:
                        routines.append(
                            RoutineTypeNode(
                                name=name,
                                signature=signature,
                                embedded=False,
                                location=location,
                                annotations=AnnotationsNode(
                                    text=annotations_text,
                                    links=self._extract_links(annotations_text),
                                ),
                                data=dict(value),
                            )
                        )

        body = BodyNode(entities=entities, routines=routines, data=dict(data))
        return body, embedded_entities, embedded_routines

    def _parse_entity(self, key: str, value: dict) -> EntityTypeNode:
        """Parse a single entity type declaration from the body."""
        # Strip -> prefix first (embedded indicator)
        clean_key, is_embedded = self._strip_embedded_prefix(key)

        # Parse mutation chain from name
        full_name_part = clean_key.split("(")[0]
        segments = full_name_part.split("::")
        actual_name = segments[-1]
        mutations = segments[:-1]
        embedded = is_embedded

        # Extract signature (everything from the first '(' onwards)
        _, signature = self._split_name_and_signature(clean_key)

        location = self._resolve_location(value.get("location", ""))
        annotations_text = value.get("annotations", "")
        if annotations_text is None:
            annotations_text = ""
        annotations_text = str(annotations_text)

        # Parse properties
        properties = self._parse_properties(value.get("properties"))

        # Parse methods
        methods = self._parse_methods(value.get("methods"))

        return EntityTypeNode(
            name=actual_name,
            signature=signature,
            location=location,
            annotations=AnnotationsNode(text=annotations_text, links=self._extract_links(annotations_text)),
            properties=properties,
            methods=methods,
            embedded=embedded,
            mutations=mutations,
            data=dict(value),
        )

    def _parse_properties(self, data: object) -> list[PropertyNode]:
        """Parse the properties dict of an entity."""
        result: list[PropertyNode] = []

        if data is None or not isinstance(data, dict):
            return result

        for prop_key, prop_value in data.items():
            key_str = str(prop_key)
            # Format: "name -> type"
            if " -> " in key_str:
                name, type_str = key_str.split(" -> ", 1)
            else:
                name = key_str
                type_str = ""

            value_text = str(prop_value) if prop_value is not None else ""
            result.append(
                PropertyNode(
                    name=name.strip(),
                    type=type_str.strip(),
                    annotations=AnnotationsNode(text=value_text, links=self._extract_links(value_text)),
                    data={prop_key: prop_value},
                )
            )

        return result

    def _parse_methods(self, data: object) -> list[MethodNode]:
        """Parse the methods dict of an entity."""
        result: list[MethodNode] = []

        if data is None or not isinstance(data, dict):
            return result

        for method_key, method_value in data.items():
            key_str = str(method_key)
            name, signature = self._split_name_and_signature(key_str)
            value_text = str(method_value) if method_value is not None else ""
            result.append(
                MethodNode(
                    name=name,
                    signature=signature,
                    annotations=AnnotationsNode(text=value_text, links=self._extract_links(value_text)),
                    data={method_key: method_value},
                )
            )

        return result

    def _parse_footer(self, data: dict, filepath: str) -> FooterNode:
        """Parse the footer section (Section 3) of the CODEMANIFEST."""
        unknown_keys = set(data.keys()) - _VALID_FOOTER_KEYS
        if unknown_keys:
            sorted_keys = ", ".join(sorted(unknown_keys))
            raise ManifestParseError(
                f"Unknown keys in footer: {sorted_keys}",
                filepath,
            )

        author = data.get("Author", "")
        created_at = data.get("CreatedAt", "")
        description = data.get("Description", "")

        return FooterNode(
            author=str(author) if author is not None else "",
            created_at=str(created_at) if created_at is not None else "",
            description=str(description) if description is not None else "",
            data=dict(data),
        )

    def _split_name_and_signature(self, key: str) -> tuple[str, str]:
        """Split a type key into (name, signature).

        name = part before the first '('
        signature = everything from '(' onwards (including the parens)
        """
        paren_idx = key.find("(")
        if paren_idx == -1:
            # No parentheses: name is the whole key, signature is empty
            return key, ""
        name = key[:paren_idx]
        signature = key[paren_idx:]

        # For mutation syntax, the name after the last :: is the actual name
        if "::" in name:
            segments = name.split("::")
            actual_name = segments[-1]
            return actual_name, signature

        return name, signature

    @staticmethod
    def _strip_embedded_prefix(name: str) -> tuple[str, bool]:
        """Strip -> prefix and return (clean_name, is_embedded)."""
        if name.startswith("->"):
            return name[2:], True
        return name, False

    def _resolve_location(self, location: str) -> str:
        """Resolve a location value to a path relative to CWD.

        If location is a bare filename, prepend self._path to make it
        relative to CWD.
        """
        if not location:
            return ""
        location = str(location)
        # If it's already a full path (contains os.sep), leave as-is
        if os.sep in location or "/" in location:
            return location
        # Bare filename: prepend self._path
        return str(Path(self._path) / location)

    @staticmethod
    def _extract_links(text: str) -> list[str]:
        """Extract backtick-enclosed link names from annotation text.

        Returns a list of all names found inside single backtick pairs (`name`).
        Only matches exactly one backtick on each side — not ``..`` or ```..```.
        Content inside multi-backtick blocks is excluded entirely.
        """
        stripped = Factory._strip_multibacktick_blocks(text)
        return Factory._find_single_backtick_names(stripped)

    @staticmethod
    def _strip_multibacktick_blocks(text: str) -> str:
        """Remove multi-backtick blocks (``..`` or ```..```), keeping single backticks."""
        cleaned: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] != "`":
                cleaned.append(text[i])
                i += 1
                continue
            j = i
            while j < n and text[j] == "`":
                j += 1
            run_len = j - i
            if run_len == 1:
                cleaned.append("`")
                i = j
                continue
            # Multi-backtick opening — find matching close
            close = j
            while close < n:
                k = close
                while k < n and text[k] == "`":
                    k += 1
                if k - close >= run_len:
                    close = k
                    break
                close = k if k > close else close + 1
            i = close
        return "".join(cleaned)

    @staticmethod
    def _find_single_backtick_names(text: str) -> list[str]:
        """Find names inside single backtick pairs in text."""
        results: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] != "`":
                i += 1
                continue
            close = text.find("`", i + 1)
            if close == -1:
                break
            content = text[i + 1 : close]
            if "\n" not in content:
                results.append(content)
            i = close + 1
        return results

    def _build_embeddings(
        self,
        import_items: list[ImportItemNode],
        embedded_entities: list[tuple[str, bool, str, dict]],
        embedded_routines: list[tuple[str, bool, str, str, dict]],
    ) -> tuple[list[tuple[str, str]], list[EntityTypeNode], list[RoutineTypeNode]]:
        """Build the embeddings list by matching embedded type names with import source paths.

        Returns:
        - list of (type_name, import_from_path) tuples for matched embedded types
        - list of EntityTypeNode for unmatched embedded entities (no matching import)
        - list of RoutineTypeNode for unmatched embedded routines (no matching import)
        """
        # Build a lookup from type name -> from_path
        import_lookup: dict[str, str] = {}
        for item in import_items:
            for type_name in item.type_name:
                import_lookup[type_name] = item.from_path

        embeddings: list[tuple[str, str]] = []
        unmatched_entities: list[EntityTypeNode] = []
        unmatched_routines: list[RoutineTypeNode] = []

        for name, _embedded, key, value in embedded_entities:
            if name in import_lookup:
                embeddings.append((name, import_lookup[name]))
            else:
                unmatched_entities.append(self._parse_entity(key, value))
        for name, _embedded, signature, text, data in embedded_routines:
            if name in import_lookup:
                embeddings.append((name, import_lookup[name]))
            else:
                unmatched_routines.append(
                    RoutineTypeNode(
                        name=name,
                        signature=signature,
                        embedded=True,
                        annotations=AnnotationsNode(text=text, links=self._extract_links(text)),
                        data=data,
                    )
                )

        return embeddings, unmatched_entities, unmatched_routines

    def _build_types_dict(self, body: BodyNode) -> dict[str, list]:
        """Build the types mapping from the body node."""
        types: dict[str, list] = {}

        for entity in body.entities:
            if entity.name not in types:
                types[entity.name] = []
            types[entity.name].append(entity)

        for routine in body.routines:
            if routine.name not in types:
                types[routine.name] = []
            types[routine.name].append(routine)

        return types

    def _collect_links(self, root: DocumentRoot) -> dict[str, list]:
        """Collect all link references from annotations in the tree."""
        links: dict[str, list] = {}

        self._collect_links_from_annotations(root.header.annotations, links)
        for item in root.header.usages.items:
            self._collect_links_from_annotations(item.annotations, links)
        for entity in root.body.entities:
            self._collect_links_from_annotations(entity.annotations, links)
            for prop in entity.properties:
                self._collect_links_from_annotations(prop.annotations, links)
            for method in entity.methods:
                self._collect_links_from_annotations(method.annotations, links)
        for routine in root.body.routines:
            self._collect_links_from_annotations(routine.annotations, links)

        return links

    def _collect_links_from_annotations(self, annotations: AnnotationsNode, links: dict[str, list]) -> None:
        """Extract link references from a single AnnotationsNode."""
        for link in annotations.links:
            if link not in links:
                links[link] = []
            links[link].append(annotations)
