# Contributing to Miktós AI Orchestration Platform

Thank you for your interest in contributing to the Miktós AI Orchestration Platform! This document provides guidelines for contributing to the project across our multiple repositories.

## Repository Structure

This project is maintained across multiple repositories:

- **[miktos-full](https://github.com/Miktos/miktos-full)**: Complete backup repository containing all code and development history
- **[miktos-core](https://github.com/Miktos/miktos-core)**: Repository optimized for private contest submission
- **[miktos-api](https://github.com/Miktos/miktos-api)**: Repository optimized for public contest submission

## Development Workflow

1. **Clone the Repository**: 
   ```bash
   git clone https://github.com/Miktos/miktos-core.git
   cd miktos-core
   ```

2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature-name
   ```

3. **Make Changes**: Implement your feature or fix

4. **Run Tests**:
   ```bash
   ./run_tests.sh
   ```

5. **Commit Your Changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

6. **Push to the Repository**:
   ```bash
   git push origin feature-name
   ```

7. **Create a Pull Request**: Visit the repository on GitHub and create a pull request from your branch

## Code Style

- Follow PEP 8 guidelines for Python code
- Write docstrings for all functions, classes, and modules
- Include unit tests for new functionality

## Testing

- Ensure all tests pass before submitting a pull request
- Add new tests for new functionality
- Maintain or improve code coverage

## Syncing Repositories

If you have access to multiple repositories, here's how to keep them in sync:

1. **Add Remote Repositories**:
   ```bash
   git remote add backup https://github.com/Miktos/miktos-full.git
   git remote add private-contest https://github.com/Miktos/miktos-core.git
   git remote add public-contest https://github.com/Miktos/miktos-api.git
   ```

2. **Push to Multiple Repositories**:
   ```bash
   git push origin your-branch
   git push backup your-branch
   git push private-contest your-branch
   git push public-contest your-branch
   ```

## Questions?

If you have any questions about contributing, please contact the project maintainers.
