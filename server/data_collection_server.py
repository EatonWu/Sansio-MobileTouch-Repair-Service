import os
import logging
from flask import Flask, request, jsonify, redirect
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flasgger import Swagger, swag_from
import sys

# Add the parent directory to the path so we can import mobile_touch_log_parsing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from TriggerString import TriggerString

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_collection_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # all in
            "model_filter": lambda tag: True,  # all in
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/swagger/"
}

swagger_template = {
    "info": {
        "title": "Data Collection Server API",
        "description": "API for collecting instances of MobileTouch database corruption",
        "version": "1.0",
    },
    "schemes": ["http", "https"],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Load environment variables or create .env file with defaults if it doesn't exist
env_file_path = os.path.join(os.path.dirname(__file__), '.env')

# Check if .env file exists
if not os.path.exists(env_file_path):
    logger.info(".env file not found. Creating with default values or from environment variables.")

    # Define default values and check if they're overridden in the environment
    env_vars = {
        'DB_USERNAME': os.environ.get('DB_USERNAME', 'postgres'),
        'DB_PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'DATABASE_HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'DATABASE_PORT': os.environ.get('DATABASE_PORT', '5432'),
        'DATABASE_NAME': os.environ.get('DATABASE_NAME', 'postgres')
    }

    # Create .env file with the values
    with open(env_file_path, 'w') as env_file:
        for key, value in env_vars.items():
            env_file.write(f"{key}={value}\n")

    logger.info(f".env file created at {env_file_path}")

# Load environment variables from .env file
load_dotenv(env_file_path)

# Initialize database connection
try:
    username = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DATABASE_HOST', 'localhost')
    port = int(os.getenv('DATABASE_PORT', 5432))
    dbname = os.getenv('DATABASE_NAME', 'postgres')

    # Create PostgreSQL connection
    conn = psycopg2.connect(
        dbname=dbname,
        user=username,
        password=password,
        host=host,
        port=port
    )
    # Create a cursor that returns results as dictionaries
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Create enum for data type if it doesn't exist
    cursor.execute("""
        DO $$ BEGIN
            CREATE TYPE data_type AS ENUM ('repair');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create table if it doesn't exist
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS repair_data
                   (
                       id            SERIAL PRIMARY KEY,
                       computer_name VARCHAR(255) NOT NULL,
                       data_type     data_type    NOT NULL DEFAULT 'repair',
                       data          JSON         NOT NULL,
                       created_at    TIMESTAMP             DEFAULT CURRENT_TIMESTAMP
                   )
                   """)

    # Create table for storing repair archive data
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS repair_archive_data
                   (
                       id            SERIAL PRIMARY KEY,
                       computer_name VARCHAR(255) NOT NULL,
                       error_type    VARCHAR(50)  NOT NULL,
                       archive_data  BYTEA        NOT NULL,
                       created_at    TIMESTAMP             DEFAULT CURRENT_TIMESTAMP
                   )
                   """)

    conn.commit()

    logger.info("Database connection established successfully")
except Exception as e:
    logger.error(f"Failed to connect to database: {str(e)}")
    conn = None
    cursor = None


@app.route('/', methods=['GET'])
def index():
    """
    Redirect to Swagger UI documentation
    ---
    responses:
      302:
        description: Redirect to Swagger UI
    """
    return redirect('/swagger/')


@app.route('/health', methods=['GET'])
@swag_from({
    'tags': ['System'],
    'summary': 'Health Check',
    'description': 'Check if the server is running and the database connection is available',
    'responses': {
        '200': {
            'description': 'Server is healthy/unhealthy',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'healthy'
                    },
                    'database': {
                        'type': 'string',
                        'example': 'connected'
                    }
                }
            }
        },
        '500': {
            'description': 'Some internal error occurred during the health check',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'Internal error'
                    },
                    'database': {
                        'type': 'string',
                        'example': 'Unknown'
                    },
                }
            }
        }
    }
})

def health_check():
    """
    Check if the server is running and the database connection is available.
    """
    global conn
    global cursor

    try:
        # attempt to connect to the database
        if conn is None or cursor is None:
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv('DATABASE_NAME', 'postgres'),
                    user=os.getenv('DB_USERNAME', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'postgres'),
                    host=os.getenv('DATABASE_HOST', 'localhost'),
                    port=int(os.getenv('DATABASE_PORT', 5432))
                )

                cursor = conn.cursor(cursor_factory=RealDictCursor)
            except Exception as db_error:
                logger.error(f"Database connection failed: {str(db_error)}")
                return jsonify({
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": str(db_error)
                }), 200

        # Test the database connection by executing a simple query
        cursor.execute("SELECT 1")
        cursor.fetchone()

        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "database": "error",
            "error": str(e)
        }), 500


@app.route('/upload_repair_data', methods=['POST'])
@swag_from({
    'tags': ['Data Collection'],
    'summary': 'Upload repair archive data',
    'description': """Endpoint to upload repair archive data.
Expects multipart/form-data with computer_name, error_type, and archive_data.
Saves the data to the database unless test=true is specified.
    """,
    'consumes': ['multipart/form-data'],
    'produces': ['application/json'],
    'parameters': [
        {
            'name': 'computer_name',
            'in': 'formData',
            'description': 'Name of the computer where the repair was performed',
            'required': True,
            'type': 'string'
        },
        {
            'name': 'error_type',
            'in': 'formData',
            'description': 'Type of error that occurred (from TriggerString enum)',
            'required': True,
            'type': 'string',
            'enum': [trigger.name for trigger in TriggerString]
        },
        {
            'name': 'archive_data',
            'in': 'formData',
            'description': 'Archived AppData folder from the bad MobileTouch instance',
            'required': True,
            'type': 'file'
        },
        {
            'name': 'test',
            'in': 'formData',
            'description': 'If true, the server will return a successful response but not add the data to the database',
            'required': False,
            'type': 'boolean',
            'default': False
        }
    ],
    'responses': {
        '201': {
            'description': 'Data successfully saved to database',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'success'
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Archive data received and saved to database'
                    },
                    'id': {
                        'type': 'integer',
                        'example': 1
                    }
                }
            }
        },
        '400': {
            'description': 'Bad request',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Missing required fields'
                    }
                }
            }
        },
        '500': {
            'description': 'Internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Failed to save data to database'
                    }
                }
            }
        }
    }
})
def upload_repair_data():
    """
    Endpoint to upload repair archive data.
    Expects multipart/form-data with computer_name, error_type, and archive_data.
    Saves the data to the database unless test=true is specified.
    """
    global conn
    global cursor

    try:
        if conn is None or cursor is None:
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv('DATABASE_NAME', 'postgres'),
                    user=os.getenv('DB_USERNAME', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'postgres'),
                    host=os.getenv('DATABASE_HOST', 'localhost'),
                    port=int(os.getenv('DATABASE_PORT', 5432))
                )

                cursor = conn.cursor(cursor_factory=RealDictCursor)
            except Exception as db_error:
                logger.error(f"Database connection failed: {str(db_error)}")
                return jsonify({"error": "Database connection is not available"}), 500

        # Check if the request contains the required fields
        if 'computer_name' not in request.form:
            logger.error("Missing computer_name in the request")
            return jsonify({"error": "Missing required field: 'computer_name'"}), 400

        if 'error_type' not in request.form:
            logger.error("Missing error_type in the request")
            return jsonify({"error": "Missing required field: 'error_type'"}), 400

        if 'archive_data' not in request.files:
            logger.error("Missing archive_data in the request")
            return jsonify({"error": "Missing required file: 'archive_data'"}), 400

        computer_name = request.form.get('computer_name')
        error_type = request.form.get('error_type')
        archive_file = request.files.get('archive_data')
        test_mode = request.form.get('test', 'false').lower() in ('true', 't', 'yes', 'y', '1')

        # Validate computer_name
        if not computer_name:
            logger.error("Computer name is required but not provided")
            return jsonify({"error": "Computer name is required"}), 400

        # Validate error_type
        try:
            # Check if error_type is a valid TriggerString name
            TriggerString[error_type]
        except KeyError:
            logger.error(f"Invalid error_type: {error_type}")
            return jsonify({"error": f"Invalid error_type. Must be one of: {[trigger.name for trigger in TriggerString]}"}), 400

        # Read the archive file
        archive_data = archive_file.read()
        if not archive_data:
            logger.error("Archive data is empty")
            return jsonify({"error": "Archive data cannot be empty"}), 400

        try:
            # If test mode is enabled, don't insert into the database
            if test_mode:
                logger.info(f"Test mode enabled. Not saving data to database for computer: {computer_name}, error_type: {error_type}")
                return jsonify({
                    "status": "success", 
                    "message": "Test mode: Archive data received but not saved to database",
                    "id": None,
                    "test": True
                }), 201

            # Insert data into the repair_archive_data table
            cursor.execute(
                "INSERT INTO repair_archive_data (computer_name, error_type, archive_data) VALUES (%s, %s, %s) RETURNING id",
                (computer_name, error_type, psycopg2.Binary(archive_data))
            )
            result = cursor.fetchone()
            conn.commit()

            return jsonify({
                "status": "success", 
                "message": "Archive data received and saved to database",
                "id": result['id'],
                "test": False
            }), 201

        except Exception as db_error:
            conn.rollback()
            logger.error(f"Failed to save archive data to database: {str(db_error)}")
            return jsonify({"error": f"Failed to save archive data to database: {str(db_error)}"}), 500

    except Exception as e:
        logger.exception("Error processing upload request")
        return jsonify({"error": str(e)}), 500


@app.route('/retrieve_appdata/<int:archive_id>', methods=['GET'])
@swag_from({
    'tags': ['Data Collection'],
    'summary': 'Retrieve AppData archive',
    'description': 'Retrieve a specific AppData archive by ID',
    'parameters': [
        {
            'name': 'archive_id',
            'in': 'path',
            'description': 'ID of the archive to retrieve',
            'required': True,
            'type': 'integer'
        }
    ],
    'responses': {
        '200': {
            'description': 'Archive data retrieved successfully',
            'content': {
                'application/zip': {
                    'schema': {
                        'type': 'string',
                        'format': 'binary'
                    }
                }
            }
        },
        '404': {
            'description': 'Archive not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Archive not found'
                    }
                }
            }
        },
        '500': {
            'description': 'Internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Failed to retrieve archive data'
                    }
                }
            }
        }
    }
})
def retrieve_appdata(archive_id):
    """
    This endpoint retrieves a specific AppData folder from the database.
    Takes the serial id.
    :param archive_id: ID of the archive to retrieve
    :return: Archive data as a downloadable file
    """
    global conn
    global cursor

    try:
        if conn is None or cursor is None:
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv('DATABASE_NAME', 'postgres'),
                    user=os.getenv('DB_USERNAME', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'postgres'),
                    host=os.getenv('DATABASE_HOST', 'localhost'),
                    port=int(os.getenv('DATABASE_PORT', 5432))
                )

                cursor = conn.cursor(cursor_factory=RealDictCursor)
            except Exception as db_error:
                logger.error(f"Database connection failed: {str(db_error)}")
                return jsonify({"error": "Database connection is not available"}), 500

        # Query the database for the archive data
        cursor.execute(
            "SELECT computer_name, error_type, archive_data, created_at FROM repair_archive_data WHERE id = %s",
            (archive_id,)
        )
        result = cursor.fetchone()

        if not result:
            logger.error(f"Archive with ID {archive_id} not found")
            return jsonify({"error": f"Archive with ID {archive_id} not found"}), 404

        # Extract the archive data
        computer_name = result['computer_name']
        error_type = result['error_type']
        archive_data = result['archive_data']
        created_at = result['created_at']

        # Create a filename for the download
        filename = f"mobiletouch_appdata_{computer_name}_{error_type}_{created_at.strftime('%Y%m%d_%H%M%S')}.zip"

        # Return the archive data as a downloadable file
        from flask import send_file
        import io
        return send_file(
            io.BytesIO(archive_data),
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.exception(f"Error retrieving archive data: {str(e)}")
        return jsonify({"error": f"Failed to retrieve archive data: {str(e)}"}), 500


@app.route('/list_incidents', methods=['GET'])
@swag_from({
    'tags': ['Data Collection'],
    'summary': 'List repair incidents',
    'description': 'Returns a paginated list of repair incidents ordered by most recent first',
    'parameters': [
        {
            'name': 'page',
            'in': 'query',
            'description': 'Page number (1-based)',
            'required': False,
            'type': 'integer',
            'default': 1
        },
        {
            'name': 'per_page',
            'in': 'query',
            'description': 'Number of items per page',
            'required': False,
            'type': 'integer',
            'default': 10,
            'minimum': 1,
            'maximum': 100
        }
    ],
    'responses': {
        '200': {
            'description': 'List of incidents',
            'schema': {
                'type': 'object',
                'properties': {
                    'incidents': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {
                                    'type': 'integer',
                                    'example': 1
                                },
                                'computer_name': {
                                    'type': 'string',
                                    'example': 'DESKTOP-ABC123'
                                },
                                'error_type': {
                                    'type': 'string',
                                    'example': 'CORRUPT_SCHEMA'
                                },
                                'created_at': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'example': '2023-05-26T09:33:40.383Z'
                                }
                            }
                        }
                    },
                    'pagination': {
                        'type': 'object',
                        'properties': {
                            'page': {
                                'type': 'integer',
                                'example': 1
                            },
                            'per_page': {
                                'type': 'integer',
                                'example': 10
                            },
                            'total_pages': {
                                'type': 'integer',
                                'example': 5
                            },
                            'total_items': {
                                'type': 'integer',
                                'example': 42
                            }
                        }
                    }
                }
            }
        },
        '500': {
            'description': 'Internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Failed to retrieve incidents'
                    }
                }
            }
        }
    }
})
def list_incidents():
    global conn
    global cursor

    try:
        if conn is None or cursor is None:
            try:
                conn = psycopg2.connect(
                    dbname=os.getenv('DATABASE_NAME', 'postgres'),
                    user=os.getenv('DB_USERNAME', 'postgres'),
                    password=os.getenv('DB_PASSWORD', 'postgres'),
                    host=os.getenv('DATABASE_HOST', 'localhost'),
                    port=int(os.getenv('DATABASE_PORT', 5432))
                )

                cursor = conn.cursor(cursor_factory=RealDictCursor)
            except Exception as db_error:
                logger.error(f"Database connection failed: {str(db_error)}")
                return jsonify({"error": "Database connection is not available"}), 500

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 10
        if per_page > 100:
            per_page = 100

        # Calculate offset
        offset = (page - 1) * per_page

        # Get total count of incidents
        cursor.execute("SELECT COUNT(*) as count FROM repair_archive_data")
        total_items = cursor.fetchone()['count']

        # Calculate total pages
        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1

        # Query the database for incidents with pagination
        cursor.execute(
            """
            SELECT id, computer_name, error_type, created_at 
            FROM repair_archive_data 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
            """,
            (per_page, offset)
        )
        incidents = cursor.fetchall()

        # Convert incidents to a list of dictionaries
        incident_list = []
        for incident in incidents:
            incident_list.append({
                'id': incident['id'],
                'computer_name': incident['computer_name'],
                'error_type': incident['error_type'],
                'created_at': incident['created_at'].isoformat() if incident['created_at'] else None
            })

        # Prepare the response
        response = {
            'incidents': incident_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'total_items': total_items
            }
        }

        return jsonify(response), 200

    except Exception as e:
        logger.exception(f"Error retrieving incidents: {str(e)}")
        return jsonify({"error": f"Failed to retrieve incidents: {str(e)}"}), 500




@app.errorhandler(404)
@swag_from({
    'tags': ['Error Handlers'],
    'summary': 'Not Found',
    'description': 'The requested resource was not found on the server',
    'responses': {
        '404': {
            'description': 'Resource not found',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Endpoint not found'
                    }
                }
            }
        }
    }
})
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
@swag_from({
    'tags': ['Error Handlers'],
    'summary': 'Internal Server Error',
    'description': 'An unexpected error occurred on the server',
    'responses': {
        '500': {
            'description': 'Internal server error',
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {
                        'type': 'string',
                        'example': 'Internal server error'
                    }
                }
            }
        }
    }
})
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500


# Teardown function to close database connection when the application shuts down
@app.teardown_appcontext
def close_db_connection(error):
    global cursor, conn
    if cursor is not None:
        logger.info("Closing database cursor")
        cursor.close()
        cursor = None
    if conn is not None:
        logger.info("Closing database connection")
        conn.close()
        conn = None


if __name__ == '__main__':
    logger.info("Starting data collection server")

    # app.run(host='0.0.0.0', port=5000, debug=False)
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
