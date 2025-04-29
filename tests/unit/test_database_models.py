# tests/unit/test_database_models.py

import pytest
import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy.dialects.postgresql import UUID
from models.database_models import GUID, User, Project, ContextStatus

class TestGUIDType:
    """Tests for the custom GUID type used for database compatibility."""
    
    def test_guid_load_dialect_impl_postgresql(self):
        """Test GUID type with PostgreSQL dialect."""
        # Create a mock PostgreSQL dialect
        mock_dialect = MagicMock()
        mock_dialect.name = 'postgresql'
        
        # Create a mock UUID type descriptor that dialect would return
        mock_uuid_descriptor = MagicMock()
        mock_dialect.type_descriptor.return_value = mock_uuid_descriptor
        
        # Create our GUID type
        guid_type = GUID()
        
        # Call the method we're testing
        result = guid_type.load_dialect_impl(mock_dialect)
        
        # Verify dialect.type_descriptor was called with UUID()
        mock_dialect.type_descriptor.assert_called_once()
        # Verify the call argument was a UUID type
        arg = mock_dialect.type_descriptor.call_args[0][0]
        assert isinstance(arg, UUID)
        
        # Verify the result is what dialect.type_descriptor returned
        assert result == mock_uuid_descriptor
    
    def test_guid_load_dialect_impl_non_postgresql(self):
        """Test GUID type with non-PostgreSQL dialect (e.g., SQLite)."""
        # Create a mock SQLite dialect
        mock_dialect = MagicMock()
        mock_dialect.name = 'sqlite'
        
        # Create a mock String type descriptor that dialect would return
        mock_string_descriptor = MagicMock()
        mock_dialect.type_descriptor.return_value = mock_string_descriptor
        
        # Create our GUID type
        guid_type = GUID()
        
        # Call the method we're testing
        result = guid_type.load_dialect_impl(mock_dialect)
        
        # Verify dialect.type_descriptor was called with String(36)
        mock_dialect.type_descriptor.assert_called_once()
        # It's hard to check exact String(36) but we can verify it's not UUID
        arg = mock_dialect.type_descriptor.call_args[0][0]
        assert not isinstance(arg, UUID)
        
        # Verify the result is what dialect.type_descriptor returned
        assert result == mock_string_descriptor
    
    def test_guid_process_bind_param_postgresql(self):
        """Test GUID process_bind_param with PostgreSQL dialect."""
        # Create a mock PostgreSQL dialect
        mock_dialect = MagicMock()
        mock_dialect.name = 'postgresql'
        
        # Create test UUID
        test_uuid = uuid.uuid4()
        
        # Create our GUID type
        guid_type = GUID()
        
        # Call the method with various inputs
        result1 = guid_type.process_bind_param(test_uuid, mock_dialect)
        result2 = guid_type.process_bind_param(str(test_uuid), mock_dialect)
        result3 = guid_type.process_bind_param(None, mock_dialect)
        
        # For PostgreSQL, it should return the value unmodified
        assert result1 == test_uuid
        assert result2 == str(test_uuid)
        assert result3 is None
    
    def test_guid_process_bind_param_non_postgresql(self):
        """Test GUID process_bind_param with non-PostgreSQL dialect."""
        # Create a mock SQLite dialect
        mock_dialect = MagicMock()
        mock_dialect.name = 'sqlite'
        
        # Create test UUID
        test_uuid = uuid.uuid4()
        
        # Create our GUID type
        guid_type = GUID()
        
        # Call the method with various inputs
        result1 = guid_type.process_bind_param(test_uuid, mock_dialect)
        result2 = guid_type.process_bind_param(str(test_uuid), mock_dialect)
        result3 = guid_type.process_bind_param(None, mock_dialect)
        
        # For non-PostgreSQL, it should convert to string
        assert result1 == str(test_uuid)
        assert result2 == str(test_uuid)
        assert result3 is None
    
    def test_guid_process_bind_param_invalid_uuid(self):
        """Test GUID process_bind_param with invalid UUID string."""
        # Create a mock non-PostgreSQL dialect
        mock_dialect = MagicMock()
        mock_dialect.name = 'sqlite'
        
        # Create our GUID type
        guid_type = GUID()
        
        # Test with an invalid UUID string
        invalid_uuid = "not-a-uuid"
        result = guid_type.process_bind_param(invalid_uuid, mock_dialect)
        
        # Should return the string as-is
        assert result == invalid_uuid
    
    def test_guid_process_result_value_valid_uuid(self):
        """Test GUID process_result_value with valid UUID string."""
        # Create our GUID type
        guid_type = GUID()
        
        # Test with a valid UUID string
        valid_uuid_str = "00112233-4455-6677-8899-aabbccddeeff"
        result = guid_type.process_result_value(valid_uuid_str, None)
        
        # Should convert to UUID object
        assert isinstance(result, uuid.UUID)
        assert str(result) == valid_uuid_str
    
    def test_guid_process_result_value_invalid_uuid(self):
        """Test GUID process_result_value with invalid UUID string."""
        # Create our GUID type
        guid_type = GUID()
        
        # Test with an invalid UUID string
        invalid_uuid = "not-a-uuid"
        result = guid_type.process_result_value(invalid_uuid, None)
        
        # Should return the string as-is
        assert result == invalid_uuid
    
    def test_guid_process_result_value_already_uuid(self):
        """Test GUID process_result_value with a UUID object."""
        # Create our GUID type
        guid_type = GUID()
        
        # Test with a UUID object
        test_uuid = uuid.uuid4()
        result = guid_type.process_result_value(test_uuid, None)
        
        # Should return the UUID as-is
        assert result == test_uuid
    
    def test_guid_process_result_value_none(self):
        """Test GUID process_result_value with None value."""
        # Create our GUID type
        guid_type = GUID()
        
        # Test with None
        result = guid_type.process_result_value(None, None)
        
        # Should return None
        assert result is None