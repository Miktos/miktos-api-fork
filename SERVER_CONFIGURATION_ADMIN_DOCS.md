# Miktos Backend: Server Configuration and Admin Features

## Server Configuration

### Overview

The Miktos backend server now includes a robust configuration system that allows for easy customization of server behavior without modifying source code. The configuration system is built around a central configuration file and environment variables, and includes sensible defaults for most settings.

### Configuration File

The server configuration is primarily managed through the `config/server_config.py` file, which defines default settings for various aspects of the server:

```python
# Server settings
SERVER_HOST = "127.0.0.1"  # Default host
SERVER_PORT = 8000         # Default port
SERVER_WORKERS = 1         # Number of worker processes
DEBUG_MODE = False         # Debug mode flag
RELOAD = False             # Auto-reload on file changes (dev mode)

# API Settings
API_PREFIX = "/api/v1"     # API base URL prefix
CORS_ORIGINS = ["*"]       # Allow all origins by default

# Security Settings
AUTH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
PASSWORD_MIN_LENGTH = 8

# Database Settings
DATABASE_URL = "sqlite:///miktos_local.db"  # Default SQLite database
```

### Environment Variables

All server configuration settings can be overridden using environment variables with the prefix `MIKTOS_`. For example:

- `MIKTOS_SERVER_PORT=9000` - Changes the server port to 9000
- `MIKTOS_DEBUG_MODE=true` - Enables debug mode
- `MIKTOS_DATABASE_URL=postgresql://user:pass@localhost/miktos` - Use PostgreSQL instead of SQLite

### Logging Configuration

The server now features comprehensive logging with different log levels and output formats:

- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log formats: JSON (structured logging) or plain text
- Log destinations: Console, file, or both

You can configure logging through environment variables:

- `MIKTOS_LOG_LEVEL=DEBUG` - Sets the logging level
- `MIKTOS_LOG_FORMAT=json` - Sets structured JSON logging
- `MIKTOS_LOG_FILE=/var/log/miktos/server.log` - Logs to a file

### Graceful Shutdown

The server now supports graceful shutdown, which ensures:

1. No new requests are accepted
2. In-progress requests are allowed to complete (with a timeout)
3. Resources are properly released
4. Database connections are properly closed

The graceful shutdown is triggered by sending a SIGTERM signal to the server process, which can be done through the admin dashboard or using the `server_manager.py` script.

## Admin Features

### Admin Dashboard Overview

The Miktos backend now includes a web-based admin dashboard that provides monitoring and management capabilities for administrators. The dashboard is accessible at `/api/v1/admin` and requires admin authentication.

### Admin API Endpoints

#### System Statistics

- **Endpoint:** `GET /api/v1/admin/stats`
- **Description:** Returns system-wide statistics including user counts, message counts, project counts, and cache usage.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  {
    "users": {
      "total": 120,
      "active": 85
    },
    "projects": {
      "total": 305,
      "by_status": {
        "NONE": 25,
        "PENDING": 48,
        "PROCESSING": 12,
        "COMPLETED": 220
      }
    },
    "messages": {
      "total": 15280,
      "last_24h": 2430
    },
    "system": {
      "version": "0.2.0",
      "environment": "production",
      "server_time": "2025-05-12T12:34:56.789012"
    },
    "cache": {
      "total_keys": 852,
      "hit_rate": 0.78,
      "memory_usage_mb": 156.2
    }
  }
  ```

#### User Management

- **Endpoint:** `GET /api/v1/admin/users`
- **Description:** Returns a list of all users in the system with basic information.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  [
    {
      "id": "user-uuid-1",
      "email": "user1@example.com",
      "is_active": true,
      "is_admin": false,
      "created_at": "2025-01-15T10:30:45.123456",
      "project_count": 12
    },
    {
      "id": "user-uuid-2",
      "email": "admin@example.com",
      "is_active": true,
      "is_admin": true,
      "created_at": "2024-11-20T14:15:22.654321",
      "project_count": 5
    }
  ]
  ```

#### Cache Management

- **Endpoint:** `POST /api/v1/admin/cache/invalidate/{model_id}`
- **Description:** Invalidates cached responses for a specific model.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  {
    "success": true,
    "model_id": "openai/gpt-4",
    "entries_removed": 245,
    "timestamp": "2025-05-12T12:34:56.789012"
  }
  ```

#### System Health Monitoring

- **Endpoint:** `GET /api/v1/admin/system/health`
- **Description:** Returns detailed system health information including database connection status, cache status, and system resource usage.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  {
    "status": "ok",
    "timestamp": "2025-05-12T12:34:56.789012",
    "components": {
      "database": {
        "status": "ok",
        "details": "Connected to SQLite database"
      },
      "cache": {
        "status": "ok",
        "details": "Redis connection established"
      }
    },
    "process_info": {
      "pid": 12345,
      "cpu_percent": 2.7,
      "memory_percent": 1.5,
      "threads": 4,
      "open_files": 8,
      "connections": 3,
      "create_time": 1683456789.12
    },
    "version": "0.2.0"
  }
  ```

#### Server Process Management

- **Endpoint:** `GET /api/v1/admin/server/processes`
- **Description:** Returns information about all running server processes.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  {
    "count": 2,
    "servers": [
      {
        "host": "127.0.0.1",
        "port": "8000",
        "pid": 12345,
        "uptime": "2d 5h 12m 36s",
        "uptime_seconds": 192756,
        "cpu_percent": 2.5,
        "memory_percent": 1.8,
        "threads": 4
      },
      {
        "host": "127.0.0.1",
        "port": "8001",
        "pid": 12346,
        "uptime": "1d 3h 45m 12s",
        "uptime_seconds": 100712,
        "cpu_percent": 3.1,
        "memory_percent": 2.0,
        "threads": 4
      }
    ],
    "timestamp": "2025-05-12T12:34:56.789012"
  }
  ```

- **Endpoint:** `POST /api/v1/admin/server/stop/{pid}`
- **Description:** Stops a specific server process with graceful shutdown.
- **Authentication:** Admin only
- **Example Response:**
  ```json
  {
    "success": true,
    "pid": 12345,
    "message": "Server process gracefully stopped",
    "timestamp": "2025-05-12T12:34:56.789012"
  }
  ```

#### User Activity Monitoring

- **Endpoint:** `GET /api/v1/admin/users/activity`
- **Description:** Returns detailed user activity statistics and analytics.
- **Authentication:** Admin only
- **Query Parameters:**
  - `days`: Number of days to look back for activity data (default: 7)
- **Example Response:**
  ```json
  {
    "activity_by_type": {
      "login": 128,
      "api_call": 1856,
      "logout": 95
    },
    "active_users": [
      {
        "user_id": "user-uuid-1",
        "activity_count": 253
      },
      {
        "user_id": "user-uuid-2",
        "activity_count": 187
      }
    ],
    "popular_endpoints": [
      {
        "endpoint": "/api/v1/generate",
        "access_count": 580
      },
      {
        "endpoint": "/api/v1/projects/{project_id}/messages",
        "access_count": 425
      }
    ],
    "timeframe_days": 7,
    "timestamp": "2025-05-12T12:34:56.789012"
  }
  ```

### User Activity Monitoring

The admin dashboard provides comprehensive visibility into user activity patterns through the dedicated user activity tracking system:

1. **Active Users Tracking:** 
   - Track currently active users and their session duration
   - View a ranked list of most active users over configurable time periods
   - See login frequency and patterns by user

2. **API Usage Patterns:** 
   - Monitor which endpoints are most heavily used
   - Track API call response times and status codes
   - Analyze endpoint popularity over time with detailed metrics

3. **Resource Consumption:** 
   - Identify which users or projects consume the most resources
   - Monitor activity trends with daily/weekly/monthly breakdowns
   - Get detailed user activity timelines for auditing purposes

4. **Activity Types:**
   - Login events (successful and failed attempts)
   - API call tracking with endpoint details
   - Administrative actions for audit trails

### Security Features

1. **Role-based Access Control:** The admin dashboard is protected by a role-based authentication system
2. **Audit Logging:** All admin actions are logged for accountability
3. **Rate Limiting:** Protection against excessive requests

## How to Access Admin Features

1. **Authentication:** Log in with an admin user account
2. **Navigate to Admin Dashboard:** Access `/api/v1/admin/stats` in your browser or API client
3. **API Access:** All admin endpoints are accessible via the API for integration with monitoring tools

## Best Practices for Server Management

1. **Regular Monitoring:** Check server health and resource usage regularly
2. **Database Maintenance:** Monitor database size and performance
3. **Cache Management:** Clear caches periodically for models that are no longer in use
4. **Log Analysis:** Review logs for errors and unusual patterns
5. **Resource Planning:** Use usage statistics to plan for scaling
