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

4. Set up environment variables:
   ```bash
   # Create a .env file in the project root
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. Run database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the development server:
   ```bash
   python simple_run.py
   # Or alternatively:
   uvicorn main:app --reload
   ```

7. The API will be available at: http://localhost:8000
   - API Documentation: http://localhost:8000/api/v1/docs
   - ReDoc Documentation: http://localhost:8000/api/v1/redoc

### Docker Deployment
1. Build and start the containers:
   ```bash
   docker-compose up -d --build
   ```

2. The API will be available at: http://localhost:8000

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
│   └── rate_limiter.py
├── models/           # Database models
├── repositories/     # Data access layer
├── schemas/          # Pydantic schemas
├── services/         # Service layer
├── utils/            # Utility functions
└── tests/            # Test suite
```

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