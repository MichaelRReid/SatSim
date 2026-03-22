"""UCI message XML validation against the XSD schema."""

from lxml import etree
from satsim.uci.schema_loader import load_schema


class UCIValidationError(Exception):
    """Raised when a UCI message fails XSD validation."""

    def __init__(self, errors: list):
        self.errors = errors
        msg = f"UCI validation failed with {len(errors)} error(s):\n" + "\n".join(errors)
        super().__init__(msg)


class UCIValidator:
    """Validates UCI XML messages against the XSD schema."""

    def __init__(self):
        self._schema = load_schema()

    def validate(self, xml_string: str) -> tuple:
        """Validate an XML string against the UCI XSD schema.

        Args:
            xml_string: The XML document string to validate.

        Returns:
            Tuple of (is_valid: bool, errors: list[str]).
        """
        try:
            doc = etree.fromstring(xml_string.encode('utf-8') if isinstance(xml_string, str) else xml_string)
        except etree.XMLSyntaxError as e:
            return False, [f"XML syntax error: {e}"]

        is_valid = self._schema.validate(doc)
        if is_valid:
            return True, []

        errors = [str(err) for err in self._schema.error_log]
        return False, errors

    def validate_or_raise(self, xml_string: str) -> None:
        """Validate XML and raise UCIValidationError on failure."""
        is_valid, errors = self.validate(xml_string)
        if not is_valid:
            raise UCIValidationError(errors)
