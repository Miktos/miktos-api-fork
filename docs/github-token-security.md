# GitHub Token Security Issue and Remediation

## Issue Identified

During a security audit of the repository synchronization process, we discovered that GitHub Personal Access Tokens (PATs) are embedded directly in Git remote URLs. This practice poses significant security risks:

1. **Token Exposure**: Tokens embedded in URLs are stored in Git configuration files and can be accessed by anyone with access to the repository or local system.
2. **Broad Access**: The exposed token has repository and workflow access scopes, providing significant permissions.
3. **No Expiration**: The token appears to be a long-lived token without proper rotation.

## Immediate Actions Required

1. **Revoke Compromised Token**:
   - Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
   - Locate and revoke any tokens that appear in the repository history
   - Revoke all tokens immediately if you're unsure which ones are compromised

2. **Update Remote URLs**:
   ```bash
   # Configure Git to use the credential helper
   git config --global credential.helper osxkeychain  # For macOS
   # or
   git config --global credential.helper store  # For Linux/Windows

   # Update remotes to use URLs without embedded tokens
   git remote set-url backup https://github.com/Miktos/miktos-full.git
   git remote set-url org_fork https://github.com/Miktos/miktos-api-fork.git
   git remote set-url origin https://github.com/Miktos/Bible.git
   git remote set-url public-contest https://github.com/Miktos/miktos-api.git
   ```

3. **Create a New Token with Restrictions**:
   - Create a new GitHub PAT with:
     - Limited scope (repo, workflow)
     - Expiration date (30-90 days)
     - Repository restrictions if possible
   - Use it once when pushing, and let the credential helper securely store it

## Preventive Measures

1. **Use Credential Helpers**:
   - Configure Git to use secure credential storage for your OS
   - This keeps tokens in your system's secure storage, not in plaintext files

2. **Use GitHub Actions Tokens**:
   - For CI/CD operations, use `${{ secrets.GITHUB_TOKEN }}`
   - These tokens are automatically managed by GitHub and have appropriate scopes
   - They expire after each workflow run

3. **Implement Token Expiration**:
   - Set all PATs to expire after a reasonable time (30-90 days)
   - Implement a rotation schedule for all access tokens

4. **Regular Security Audits**:
   - Periodically review Git history and configuration for exposed tokens
   - Scan repositories for secrets using GitHub Secret Scanning or similar tools

## Technical Implementation

1. **Secure GitHub Actions Workflows**:
   ```yaml
   # Example of secure token usage in GitHub Actions
   steps:
     - uses: actions/checkout@v3
       with:
         token: ${{ secrets.GITHUB_TOKEN }}
   
     - name: Push to repository
       uses: ad-m/github-push-action@master
       with:
         github_token: ${{ secrets.GITHUB_TOKEN }}
         repository: Organization/repo-name
   ```

2. **Local Development Workflow**:
   ```bash
   # One-time setup
   git config --global credential.helper store
   
   # Clone without token in URL
   git clone https://github.com/Organization/repo-name.git
   
   # When pushing for the first time, enter credentials once
   # Git will securely store them for future operations
   ```

By implementing these security measures, we can prevent token exposure and maintain secure access to our repositories.
