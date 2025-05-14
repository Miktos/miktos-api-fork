#!/bin/bash
# Script to sync changes across Miktos repositories
# Based on the GitHub workflow: .github/workflows/sync-repos.yml

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Display script header
echo -e "${BLUE}===== Miktós Repository Sync Tool =====${NC}"
echo -e "This script will sync your changes across all Miktós repositories.\n"

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${BLUE}Current branch:${NC} $CURRENT_BRANCH"

# Check for uncommitted changes
echo -e "${BLUE}Checking for uncommitted changes...${NC}"
if git status --porcelain | grep -q "^.M\|^??" ; then
    echo -e "${YELLOW}You have uncommitted changes:${NC}"
    git status --short

    # Ask if user wants to commit these changes
    read -p "Do you want to commit these changes before syncing? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stage all changes
        echo -e "${BLUE}Staging changes...${NC}"
        git add .

        # Ask for commit message
        echo -e "${BLUE}Enter a commit message:${NC}"
        read -r commit_msg

        # Commit the changes
        git commit -m "$commit_msg"

        # Check if pre-commit hooks modified files but didn't commit them
        if git status --porcelain | grep -q "^.M\|^??" ; then
            echo -e "${YELLOW}Pre-commit hooks modified some files. Committing these changes as well...${NC}"
            git add .
            git commit -m "Auto-fixes from pre-commit hooks"
        fi

        echo -e "${GREEN}Changes committed successfully.${NC}"
    else
        echo -e "${YELLOW}Proceeding without committing changes. Only previously committed changes will be synced.${NC}"
    fi
else
    echo -e "${GREEN}No uncommitted changes detected.${NC}"
fi

# Confirm with user
read -p "Do you want to sync branch '$CURRENT_BRANCH' to all repositories? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${RED}Operation cancelled.${NC}"
    exit 0
fi

# Function to check if a remote exists
remote_exists() {
    git remote | grep -q "^$1$"
    return $?
}

# Function to add remote if it doesn't exist
add_remote_if_needed() {
    local remote_name=$1
    local remote_url=$2

    if ! remote_exists $remote_name; then
        echo -e "${BLUE}Adding remote:${NC} $remote_name -> $remote_url"
        git remote add $remote_name $remote_url
    else
        echo -e "${GREEN}Remote '$remote_name' already exists.${NC}"
    fi
}

# 1. Ensure all remotes are configured correctly
echo -e "\n${BLUE}Configuring repository remotes...${NC}"
add_remote_if_needed "backup" "https://github.com/Miktos/miktos-full.git"
add_remote_if_needed "public-contest" "https://github.com/Miktos/miktos-api.git"
add_remote_if_needed "org_fork" "https://github.com/Miktos/miktos-api-fork.git"

# 2. Push to backup repository
echo -e "\n${BLUE}Pushing to backup repository (miktos-full)...${NC}"
git push backup $CURRENT_BRANCH
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to push to backup repository. Please check your permissions.${NC}"
else
    echo -e "${GREEN}Successfully pushed to backup repository.${NC}"
fi

# 3. Create a temporary branch for the public repositories (removing sensitive files)
echo -e "\n${BLUE}Creating a clean branch for public repositories...${NC}"
PUBLIC_TEMP_BRANCH="public-temp-$(date +%s)"
git checkout -b $PUBLIC_TEMP_BRANCH

echo -e "${BLUE}Removing sensitive files for public repositories...${NC}"
# Remove sensitive files (similar to GitHub workflow)
git rm -rf --cached .env* **/secrets/ **/credentials.* **/*config.private.* 2>/dev/null || echo -e "${BLUE}No sensitive files matched patterns.${NC}"
git rm -rf --cached *.db *.sqlite dump.rdb 2>/dev/null || echo -e "${BLUE}No database files matched patterns.${NC}"

# Commit changes if there are any
git diff --cached --quiet
if [ $? -ne 0 ]; then
    git commit -m "Remove sensitive files for public repo sync"
    echo -e "${GREEN}Committed changes to remove sensitive files.${NC}"
else
    echo -e "${BLUE}No sensitive files to remove.${NC}"
fi

# 4. Handle public API repository (miktos-api)
echo -e "\n${BLUE}Handling public API repository (miktos-api)...${NC}"
echo -e "${BLUE}Note: miktos-api has strict branch protection rules.${NC}"
echo -e "${YELLOW}IMPORTANT: You need to manually create a PR through the GitHub interface.${NC}"
echo -e "${YELLOW}You can do this by going to: https://github.com/Miktos/miktos-api/pulls${NC}"
echo -e "${YELLOW}and using the GitHub Actions workflow in the main repository.${NC}"
echo -e "${GREEN}The recommended approach is to push to the main branch in the origin repository,${NC}"
echo -e "${GREEN}which will trigger the GitHub Actions workflow to sync properly.${NC}"

# Check if we need to push to origin
git remote | grep -q "^origin$"
if [ $? -eq 0 ]; then
    read -p "Do you want to push to origin to trigger the GitHub Actions workflow? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Pushing to origin to trigger workflow...${NC}"
        git checkout $CURRENT_BRANCH

        # Push to origin
        git push origin $CURRENT_BRANCH
        if [ $? -ne 0 ]; then
            echo -e "${YELLOW}Initial push to origin failed. This might be an authentication issue.${NC}"
            echo -e "${YELLOW}If you have a Personal Access Token (PAT), you can enter it now to authenticate.${NC}"
            echo -e "${YELLOW}Leave blank to skip this step.${NC}"
            read -p "Enter your GitHub PAT (input will be hidden): " -s pat
            echo

            if [ ! -z "$pat" ]; then
                # Get the remote URL without the protocol
                origin_url=$(git remote get-url origin | sed 's/https:\/\///')
                # Push using the PAT
                git push https://$pat@$origin_url $CURRENT_BRANCH
                if [ $? -ne 0 ]; then
                    echo -e "${RED}Failed to push to origin even with PAT. Please check your permissions.${NC}"
                else
                    echo -e "${GREEN}Successfully pushed to origin using PAT. GitHub Actions workflow will sync repositories.${NC}"
                fi
            else
                echo -e "${RED}No PAT provided. Failed to push to origin. Please check your permissions.${NC}"
            fi
        else
            echo -e "${GREEN}Successfully pushed to origin. GitHub Actions workflow will sync repositories.${NC}"
        fi
    else
        echo -e "${YELLOW}Skipping push to origin. Remember to manually sync repositories.${NC}"
    fi
fi

# 5. Push to organization fork
echo -e "\n${BLUE}Pushing to organization fork (miktos-api-fork)...${NC}"
git push org_fork $PUBLIC_TEMP_BRANCH:$CURRENT_BRANCH -f
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to push to organization fork. Please check your permissions.${NC}"
else
    echo -e "${GREEN}Successfully pushed to organization fork.${NC}"
fi

# 6. Clean up: Switch back to original branch and delete temp branch
echo -e "\n${BLUE}Cleaning up...${NC}"
git checkout $CURRENT_BRANCH
git branch -D $PUBLIC_TEMP_BRANCH
echo -e "${GREEN}Deleted temporary branch $PUBLIC_TEMP_BRANCH${NC}"

echo -e "\n${GREEN}Repository sync complete!${NC}"
echo -e "${BLUE}Changes from branch $CURRENT_BRANCH have been pushed to:${NC}"
echo -e "  - ${GREEN}backup${NC} (Miktos/miktos-full)"
echo -e "  - ${YELLOW}public-contest${NC} (Miktos/miktos-api) - Use GitHub Actions workflow for syncing"
echo -e "  - ${GREEN}org_fork${NC} (Miktos/miktos-api-fork)"
echo -e "\nIf you encountered any authentication issues, please ensure your Git credentials are set up correctly."

echo -e "\n${GREEN}Repository sync completed!${NC}"
echo -e "${BLUE}Note:${NC} If any pushes failed, you may need to set up authentication or check your permissions."
echo -e "For automated GitHub Actions sync, push to the 'main' branch which will trigger the workflow.\n"
