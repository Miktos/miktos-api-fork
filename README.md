# Miktós AI Orchestration Platform - Backend

Core backend engine for the Miktós AI Orchestration Platform.

## Overview

Miktós provides a unified interface to interact with multiple AI models (OpenAI, Anthropic, Google) through a single API. The platform intelligently routes requests, handles streaming responses, and provides a consistent interface regardless of the underlying model provider.

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- API keys for supported model providers (OpenAI, Anthropic, Google)
- Docker and Docker Compose (optional, for containerized deployment)

### Local Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/YourUsername/miktos-core.git
   cd miktos-core