# GitHub Token Remediation Guide

## Issue Summary

A GitHub Personal Access Token was accidentally committed to the repository, and while we've redacted it from the files:

- The token has been redacted from `docs/github-token-security.md`
- The token has been redacted from `.env`
- The Git remotes have been updated using `secure_git_remotes.sh` to use secure authentication

However, GitHub's push protection is still detecting the token in the commit history, preventing push operations to protected repositories like `miktos-api-fork`.

## Immediate Actions

1. **Revoke the Exposed Token**:
   - Visit [GitHub Personal Access Tokens](https://github.com/settings/tokens)
   - Locate and revoke the compromised token
   - Create a new token with appropriate scopes and an expiration date

2. **Bypass GitHub's Push Protection** (Choose one option):

   **Option A - Allow Push from GitHub Interface**:
   - Go to the push rejection notification in the GitHub interface
   - Use GitHub's "I understand, allow me to push this secret" option (requires admin privileges)
   - This is a temporary bypass that should only be used after the token has been revoked

   **Option B - Create a Fresh Clone and Apply Changes**:
   ```bash
   # Create a new, clean clone without the token in history
   git clone https://github.com/Miktos/miktos-api-fork.git miktos-api-fork-clean
   cd miktos-api-fork-clean

   # Create a new branch for your changes
   git checkout -b docs/enhanced-cicd-security

   # Apply your changes (export a patch from your current repo if necessary)
   # git apply ~/path/to/your/changes.patch

   # Or manually copy over the changed files, but NOT the ones with tokens

   # Commit and push the changes to the clean repository
   git add .
   git commit -m "Enhance CI/CD security without exposing tokens"
   git push origin docs/enhanced-cicd-security
   ```

3. **Configure Secret Scanning**:
   - Enable GitHub's secret scanning for the repository
   - Visit https://github.com/Miktos/miktos-api-fork/settings/security_analysis
   - Enable "Secret scanning" under the "Code security and analysis" section
   - This will help catch any future token exposures before they become problematic

## Long-term Remediation Steps

1. **Update the CI/CD Workflow**:
   - Modify the GitHub Actions workflow to use GitHub's built-in token instead of embedded tokens
   - Use `${{ secrets.GITHUB_TOKEN }}` which is automatically provided by GitHub Actions
   - This token has the necessary permissions for most repository operations and is securely managed by GitHub

2. **Implement Token Rotation**:
   - Create a schedule for regular token rotation (every 30-90 days)
   - Update documentation to reflect this policy

3. **Developer Training**:
   - Ensure all team members are aware of the proper handling of secrets
   - Provide guidelines for using credential helpers and environment variables

## Monitoring and Verification

1. **Regular Audits**:
   - Conduct periodic audits of Git history and configurations
   - Use tools like `gitleaks` or GitHub's secret scanning to detect exposed tokens

2. **Verify Secure Configurations**:
   - Regularly check that all Git remotes are using secure authentication methods
   - Run `secure_git_remotes.sh` as a maintenance task
