"""XSD schema loader for UCI message validation."""

import os
from functools import lru_cache
from lxml import etree


_SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'schemas')
_DEFAULT_SCHEMA = os.path.join(_SCHEMA_DIR, 'uci_v6.xsd')


@lru_cache(maxsize=1)
def load_schema(schema_path: str = None) -> etree.XMLSchema:
    """Load and cache the UCI XSD schema.

    Args:
        schema_path: Path to the XSD file. Defaults to schemas/uci_v6.xsd.

    Returns:
        Compiled lxml XMLSchema object.
    """
    if schema_path is None:
        schema_path = _DEFAULT_SCHEMA
    schema_path = os.path.abspath(schema_path)
    with open(schema_path, 'rb') as f:
        schema_doc = etree.parse(f)
    return etree.XMLSchema(schema_doc)


def get_schema_path() -> str:
    """Return the absolute path to the default UCI XSD schema."""
    return os.path.abspath(_DEFAULT_SCHEMA)
