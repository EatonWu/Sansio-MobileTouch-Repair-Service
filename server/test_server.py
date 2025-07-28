import pytest
import json
import os
import io
from unittest.mock import patch, MagicMock, mock_open
from data_collection_server import app, TriggerString

@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_db_connection():
    """Mock the database connection and cursor."""
    with patch('data_collection_server.conn') as mock_conn, \
         patch('data_collection_server.cursor') as mock_cursor:
        # Configure the mock cursor to return a dictionary with an 'id' key
        mock_cursor.fetchone.return_value = {'id': 1}
        yield mock_conn, mock_cursor

def test_index_endpoint(client):
    """Test the index endpoint redirects to Swagger UI."""
    response = client.get('/')
    assert response.status_code == 302  # Redirect status code
    assert '/swagger/' in response.location

def test_upload_data_valid_json(client, mock_db_connection):
    """Test the upload_data endpoint with valid JSON data."""
    mock_conn, mock_cursor = mock_db_connection

    # Valid JSON data
    test_data = {
        "computer_name": "test-computer",
        "repair_type": "test-repair",
        "timestamp": "2025-07-22T12:00:00Z",
        "details": {
            "error_code": "TEST-001",
            "description": "Test error"
        }
    }

    # Note: The server's SQL query only inserts into the 'data' column,
    # even though the table schema requires 'computer_name' and 'data'.
    # This test matches the actual implementation.

    response = client.post(
        '/upload_data',
        data=json.dumps(test_data),
        content_type='application/json'
    )

    # Check response
    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert response_data['status'] == 'success'
    assert 'id' in response_data

    # Verify database operations were called
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

def test_upload_data_not_json(client):
    """Test the upload_data endpoint with non-JSON data."""
    response = client.post(
        '/upload_data',
        data="This is not JSON",
        content_type='text/plain'
    )

    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert 'Request must be JSON' in response_data['error']

def test_upload_data_empty_json(client):
    """Test the upload_data endpoint with empty JSON data."""
    response = client.post(
        '/upload_data',
        data=json.dumps({}),
        content_type='application/json'
    )

    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert 'No data provided' in response_data['error']

def test_upload_data_db_connection_error(client):
    """Test the upload_data endpoint when database connection is not available."""
    with patch('data_collection_server.conn', None), \
         patch('data_collection_server.cursor', None):

        test_data = {"test": "data"}
        response = client.post(
            '/upload_data',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert 'error' in response_data
        assert 'Database connection is not available' in response_data['error']

def test_upload_data_db_error(client, mock_db_connection):
    """Test the upload_data endpoint when a database error occurs."""
    mock_conn, mock_cursor = mock_db_connection

    # Configure the mock cursor to raise an exception
    mock_cursor.execute.side_effect = Exception("Database error")

    test_data = {"test": "data"}
    response = client.post(
        '/upload_data',
        data=json.dumps(test_data),
        content_type='application/json'
    )

    assert response.status_code == 500
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert 'Failed to save data to database' in response_data['error']

    # Verify rollback was called
    mock_conn.rollback.assert_called_once()

def test_not_found_error(client):
    """Test the 404 error handler."""
    response = client.get('/nonexistent_endpoint')

    assert response.status_code == 404
    response_data = json.loads(response.data)
    assert 'error' in response_data
    assert 'Endpoint not found' in response_data['error']

def test_env_file_creation():
    """Test that the .env file is created with default values if it doesn't exist."""
    # Mock environment variables
    env_vars = {
        'DB_USERNAME': 'test_user',
        'DB_PASSWORD': 'test_password',
        'DATABASE_HOST': 'test_host',
        'DATABASE_PORT': '1234',
        'DATABASE_NAME': 'test_db'
    }

    # Path to the .env file
    env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    # Mock functions
    with patch('os.path.exists', return_value=False), \
         patch('os.environ.get', side_effect=lambda key, default=None: env_vars.get(key, default)), \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('data_collection_server.load_dotenv'):

        # Re-import the module to trigger the .env file creation
        import importlib
        import data_collection_server
        importlib.reload(data_collection_server)

        # Check that the file was opened for writing
        mock_file.assert_any_call(env_file_path, 'w')

        # Check that the correct values were written to the file
        handle = mock_file()
        expected_calls = [
            f"{key}={value}\n" for key, value in env_vars.items()
        ]

        # Check each write call
        for expected_call in expected_calls:
            assert any(call.args[0] == expected_call for call in handle.write.call_args_list), \
                f"Expected write call with '{expected_call}' not found"

def test_upload_repair_data_normal(client, mock_db_connection):
    """Test the upload_repair_data endpoint with normal operation (test=false)."""
    mock_conn, mock_cursor = mock_db_connection

    # Create a test file
    test_file_content = b'Test file content'
    test_file = io.BytesIO(test_file_content)

    # Create form data
    data = {
        'computer_name': 'test-computer',
        'error_type': TriggerString.UNKNOWN.name,
        'archive_data': (test_file, 'test_archive.zip')
    }

    # Send the request
    response = client.post(
        '/upload_repair_data',
        data=data,
        content_type='multipart/form-data'
    )

    # Check response
    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert response_data['status'] == 'success'
    assert response_data['message'] == 'Archive data received and saved to database'
    assert response_data['id'] == 1
    assert response_data['test'] == False

    # Verify database operations were called
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()

def test_upload_repair_data_test_mode(client, mock_db_connection):
    """Test the upload_repair_data endpoint with test mode (test=true)."""
    mock_conn, mock_cursor = mock_db_connection

    # Create a test file
    test_file_content = b'Test file content'
    test_file = io.BytesIO(test_file_content)

    # Create form data with test=true
    data = {
        'computer_name': 'test-computer',
        'error_type': TriggerString.UNKNOWN.name,
        'archive_data': (test_file, 'test_archive.zip'),
        'test': 'true'
    }

    # Send the request
    response = client.post(
        '/upload_repair_data',
        data=data,
        content_type='multipart/form-data'
    )

    # Check response
    assert response.status_code == 201
    response_data = json.loads(response.data)
    assert response_data['status'] == 'success'
    assert response_data['message'] == 'Test mode: Archive data received but not saved to database'
    assert response_data['id'] is None
    assert response_data['test'] == True

    # Verify database operations were NOT called
    mock_cursor.execute.assert_not_called()
    mock_conn.commit.assert_not_called()
