# Miktós Repository Architecture

This document explains the architecture and relationship between the different repositories used for the Miktós AI Orchestration Platform.

## Repository Overview

The Miktós project is maintained across multiple repositories, each serving a specific purpose:

### miktos-full
- **URL**: [https://github.com/Miktos/miktos-full](https://github.com/Miktos/miktos-full)
- **Purpose**: Complete backup repository containing all code and development history
- **Access**: Private, restricted to project maintainers
- **Content**: Contains all code, including potentially sensitive configurations and development history

### miktos-core
- **URL**: [https://github.com/Miktos/miktos-core](https://github.com/Miktos/miktos-core)
- **Purpose**: Repository optimized for private contest submission
- **Access**: Private, accessible to contest judges and authorized personnel
- **Content**: Complete functional codebase with appropriate documentation for private evaluation

### miktos-api
- **URL**: [https://github.com/Miktos/miktos-api](https://github.com/Miktos/miktos-api)
- **Purpose**: Repository optimized for public contest submission
- **Access**: Public, visible to contest judges and the broader community
- **Content**: Publicly-shareable codebase with any sensitive information removed

## Repository Synchronization

### When to Sync
- After completing a significant feature
- Before contest submission deadlines
- When preparing for a release

### How to Sync
1. Ensure your local repository is up-to-date:
   ```bash
   git pull origin main
   ```

2. Push to the backup repository:
   ```bash
   git push backup main
   ```

3. Push to the private contest repository:
   ```bash
   git push private-contest main
   ```

4. For the public contest repository, create a pull request from the fork:
   ```bash
   git push org_fork main
   # Then create a PR via the GitHub web interface
   ```

## Version Tagging

We use version tags to mark significant milestones and releases:

```bash
# Create a new version tag
git tag -a v1.x -m "Version 1.x description"

# Push the tag to all repositories
git push backup --tags
git push private-contest --tags
git push org_fork --tags
```

## Branch Strategy

- `main`: Primary development branch
- `feature/*`: For new feature development
- `bugfix/*`: For bug fixes
- `release/*`: For release preparation

## Repository Configuration

Each repository may have slightly different configuration files, especially for sensitive information. Always check the following files when synchronizing:

- `.env` files (not committed to repositories)
- Configuration files in `config/` directory
- API keys and secrets references
