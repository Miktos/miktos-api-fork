# Miktós AI Orchestration Platform - Backend

Core backend engine for the Miktós AI Orchestration Platform.

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/Miktos/miktos-api/ci-cd.yml?branch=main&label=CI%2FCD)](https://github.com/Miktos/miktos-api/actions)
[![Version](https://img.shields.io/badge/version-0.2.0-blue)](https://github.com/Miktos/miktos-api)
[![License](https://img.shields.io/github/license/Miktos/miktos-api)](LICENSE)

## Overview

Miktós provides a unified interface to interact with multiple AI models (OpenAI, Anthropic, Google) through a single API. The platform intelligently routes requests, handles streaming responses, and provides a consistent interface regardless of the underlying model provider.

### Key Features

- **Unified API**: Access multiple AI models through a consistent interface
- **Intelligent Routing**: Automatic routing of requests to the specified model provider
- **Streaming Support**: Real-time streaming of AI responses using Server-Sent Events
- **Project Context**: Organize conversations into projects with context management
- **Request History**: Store and retrieve conversation history by project
- **Error Handling**: Consistent error responses across all providers
- **Rate Limiting**: Configurable rate limits to prevent abuse
- **Admin Dashboard**: Comprehensive web-based admin interface for system monitoring and management
- **Server Configuration**: Flexible configuration system for easy customization
- **Graceful Shutdown**: Ensures proper resource cleanup and request completion

## Repository Structure

This project is maintained across multiple repositories for different purposes:

- **[miktos-full](https://github.com/Miktos/miktos-full)**: Complete backup repository containing all code and development history
- **[miktos-core](https://github.com/Miktos/miktos-core)**: Repository optimized for private contest submission
- **[miktos-api](https://github.com/Miktos/miktos-api)**: Repository optimized for public contest submission

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- API keys for supported model providers (OpenAI, Anthropic, Google)
- Docker and Docker Compose (optional, for containerized deployment)

### Local Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Miktos/miktos-core.git
   cd miktos-core
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env` and fill in the required values
   - Ensure API keys for all providers are configured

### Running the Server

#### Using the Simple Run Script (Recommended)
```bash
# Start the server on default port (8000)
python simple_run.py start

# Start the server in development mode with auto-reload
python simple_run.py start --dev

# Start the server on a specific port
python simple_run.py start --port 9000

# Check server status
python simple_run.py status

# Stop the server
python simple_run.py stop
```

#### Using the Advanced Server Manager
For more control over server instances:
```bash
# Start the server with specific parameters
python server_manager.py start --host 0.0.0.0 --port 8000

# Check if server is running on a specific port
python server_manager.py status --port 8000

# Stop a specific server instance
python server_manager.py stop --pid 12345

# Stop server running on specific port
python server_manager.py stop --port 8000
```

#### Using Docker (for Production)
1. Build and start containers:
   ```bash
   docker-compose up -d
   ```

2. Stop containers:
   ```bash
   docker-compose down
   ```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Log in and get JWT token |
| GET | `/api/v1/auth/me` | Get current user info |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects` | List all user projects |
| POST | `/api/v1/projects` | Create a new project |
| GET | `/api/v1/projects/{project_id}` | Get project details |
| PATCH | `/api/v1/projects/{project_id}` | Update project |
| DELETE | `/api/v1/projects/{project_id}` | Delete project |
| GET | `/api/v1/projects/{project_id}/messages` | Get project messages |

### AI Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/generate` | Generate AI completion and store in project |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check endpoint |
| GET | `/api/v1/status` | API status information |

## Using the Server Management Tools

### Simple Runner Script

The `simple_run.py` script provides a user-friendly interface for common server operations:

```bash
# Start the server
python simple_run.py start

# Start with custom settings
python simple_run.py start --port 9000 --debug --reload

# Check server status
python simple_run.py status

# Stop server
python simple_run.py stop
```

### Advanced Server Management

For more advanced server management, use the `server_manager.py` script:

```bash
# Start server with specific settings
python server_manager.py start --host 0.0.0.0 --port 8080 --workers 4

# Find running instances
python server_manager.py find

# Stop all server instances
python server_manager.py stop

# Stop a specific instance
python server_manager.py stop --port 8080
```

These tools help prevent port conflicts and make it easier to manage server instances.

## Testing

Run the test suite with:
```bash
./run_tests.sh
```

Or with pytest directly:
```bash
pytest
```

For test coverage report:
```bash
pytest --cov=. --cov-report=html
```

## API Documentation

When the server is running, API documentation is available at:
- Swagger UI: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`

## Environment Variables

Key environment variables required for operation:

### Required Settings
- `DATABASE_URL`: Connection string for the database
- `JWT_SECRET`: Secret key for JWT token generation

### AI Provider API Keys
- `OPENAI_API_KEY`: API key for OpenAI
- `ANTHROPIC_API_KEY`: API key for Anthropic
- `GOOGLE_API_KEY`: API key for Google Gemini

### Optional Settings
- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: INFO)
- `DEBUG`: Enable debug mode (default: False)
- `ENVIRONMENT`: Environment type (development, testing, production)
- `CORS_ALLOW_ORIGINS`: Comma-separated list of allowed origins for CORS

Refer to `.env.example` for all available environment variables.

## Project Structure

```
miktos_backend/
├── api/              # API endpoints
│   ├── auth.py       # Authentication routes
│   └── endpoints.py  # Main API routes
├── config/           # Configuration
│   ├── database.py   # Database setup
│   └── settings.py   # Settings management
├── core/             # Core business logic
│   └── orchestrator.py # Request orchestration
├── integrations/     # External API clients
│   ├── openai_client.py
│   ├── claude_client.py
│   └── gemini_client.py
├── middleware/       # Middleware components
│   ├── rate_limiter.py
│   └── activity_logger.py
├── models/           # Database models
│   └── database_models.py
├── repositories/     # Data access layer
│   ├── base_repository.py
│   ├── user_repository.py
│   ├── project_repository.py
│   ├── message_repository.py
│   └── activity_repository.py
├── schemas/          # Pydantic schemas
│   └── activity.py
├── services/         # Service layer
├── utils/            # Utility functions
└── tests/            # Test suite
```

## Admin Dashboard

The system includes a comprehensive admin dashboard accessible at `/api/v1/admin` with the following features:

### System Monitoring
- **System Statistics**: User counts, message counts, project counts, and cache usage
- **Health Checks**: Database, cache, and overall system health monitoring
- **Process Information**: CPU usage, memory usage, and uptime for all server processes
- **User Activity Tracking**: Comprehensive logs of user logins and API usage patterns

### User Management
- **User Listing**: View all users with basic information and activity status
- **Project Statistics**: Track project counts and statuses across all users

### Server Management
- **Process Control**: View and manage running server processes with graceful shutdown
- **Cache Management**: Invalidate model-specific cache entries when needed

For detailed information on server configuration and administration, refer to the [SERVER_CONFIGURATION_ADMIN_DOCS.md](SERVER_CONFIGURATION_ADMIN_DOCS.md) document.

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security

If you discover a security vulnerability within this project, please send an email to security@miktos.com. All security vulnerabilities will be promptly addressed.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - The web framework used
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM library
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Python-Jose](https://python-jose.readthedocs.io/) - JWT implementation