from app.utils.document_builder import (
    extract_entity_type_from_subject,
    extract_entity_id_from_subject,
)


class TestExtractEntityTypeFromSubject:
    """Test cases for extract_entity_type_from_subject function."""

    def test_simple_entity_type_with_placeholder(self):
        """Test extracting entity type from subject with UUID placeholder."""
        subject = "pets/:uuid"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_simple_entity_type_with_id(self):
        """Test extracting entity type from subject with actual ID."""
        subject = "pets/123"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_namespaced_entity_type(self):
        """Test extracting entity type from namespaced subject."""
        subject = "com.example.pets/123"
        result = extract_entity_type_from_subject(subject)
        assert result == "com.example.pets"

    def test_entity_type_with_uuid_id(self):
        """Test extracting entity type from subject with UUID ID."""
        subject = "pets/abc-def-123"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_entity_type_with_multiple_slashes(self):
        """Test extracting entity type when subject has multiple slashes."""
        subject = "pets/123/extra"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_entity_type_with_colon_prefix(self):
        """Test extracting entity type when entity type starts with colon."""
        subject = ":pets/123"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_entity_type_no_slash(self):
        """Test extracting entity type when subject has no slash."""
        subject = "pets"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_empty_string(self):
        """Test extracting entity type from empty string."""
        subject = ""
        result = extract_entity_type_from_subject(subject)
        assert result == ""

    def test_complex_namespace(self):
        """Test extracting entity type from complex namespace."""
        subject = "com.example.api.v1.users/123"
        result = extract_entity_type_from_subject(subject)
        assert result == "com.example.api.v1.users"

    def test_entity_type_starts_with_slash(self):
        """Test extracting entity type when subject starts with slash."""
        subject = "/pets/:uuid"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_entity_type_starts_with_slash_with_id(self):
        """Test extracting entity type when subject starts with slash and has ID."""
        subject = "/pets/123"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"

    def test_entity_type_starts_with_slash_trailing_slash(self):
        """Test extracting entity type when subject starts and ends with slash."""
        subject = "/pets/:uuid/"
        result = extract_entity_type_from_subject(subject)
        assert result == "pets"


class TestExtractEntityIdFromSubject:
    """Test cases for extract_entity_id_from_subject function."""

    def test_placeholder_id(self):
        """Test extracting placeholder ID from subject."""
        subject = "pets/:uuid"
        result = extract_entity_id_from_subject(subject)
        assert result == ":uuid"

    def test_numeric_id(self):
        """Test extracting numeric ID from subject."""
        subject = "pets/123"
        result = extract_entity_id_from_subject(subject)
        assert result == "123"

    def test_uuid_id(self):
        """Test extracting UUID ID from subject."""
        subject = "pets/abc-def-123"
        result = extract_entity_id_from_subject(subject)
        assert result == "abc-def-123"

    def test_id_with_multiple_slashes(self):
        """Test extracting ID when subject has multiple slashes."""
        subject = "pets/123/extra"
        result = extract_entity_id_from_subject(subject)
        assert result == "123/extra"

    def test_id_with_special_characters(self):
        """Test extracting ID with special characters."""
        subject = "pets/abc-123_def.456"
        result = extract_entity_id_from_subject(subject)
        assert result == "abc-123_def.456"

    def test_no_slash_returns_empty(self):
        """Test extracting ID when subject has no slash returns empty string."""
        subject = "pets"
        result = extract_entity_id_from_subject(subject)
        assert result == ""

    def test_empty_string_returns_empty(self):
        """Test extracting ID from empty string returns empty string."""
        subject = ""
        result = extract_entity_id_from_subject(subject)
        assert result == ""

    def test_only_slash_returns_empty(self):
        """Test extracting ID when subject is just a slash."""
        subject = "/"
        result = extract_entity_id_from_subject(subject)
        assert result == ""

    def test_slash_at_end(self):
        """Test extracting ID when subject ends with slash."""
        subject = "pets/"
        result = extract_entity_id_from_subject(subject)
        assert result == ""

    def test_namespaced_entity_with_id(self):
        """Test extracting ID from namespaced entity subject."""
        subject = "com.example.pets/123"
        result = extract_entity_id_from_subject(subject)
        assert result == "123"

    def test_id_starts_with_slash(self):
        """Test extracting ID when subject starts with slash."""
        subject = "/pets/:uuid"
        result = extract_entity_id_from_subject(subject)
        assert result == ":uuid"

    def test_id_starts_with_slash_with_id(self):
        """Test extracting ID when subject starts with slash and has ID."""
        subject = "/pets/123"
        result = extract_entity_id_from_subject(subject)
        assert result == "123"

    def test_id_starts_with_slash_trailing_slash(self):
        """Test extracting ID when subject starts and ends with slash."""
        subject = "/pets/:uuid/"
        result = extract_entity_id_from_subject(subject)
        assert result == ":uuid"

    def test_id_starts_with_slash_namespaced(self):
        """Test extracting ID when subject starts with slash and is namespaced."""
        subject = "/com.example.pets/123"
        result = extract_entity_id_from_subject(subject)
        assert result == "123"

    def test_id_starts_with_slash_with_xxxx(self):
        """Test extracting ID when subject starts with slash and has xxxx format."""
        subject = "/pets/xxxx"
        result = extract_entity_id_from_subject(subject)
        assert result == "xxxx"
