#!/usr/bin/env python

import os
import sys
import logging
import configparser
import csv
import re
import git
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler("config_updater.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class JavaVersionConfigUpdater:
    def __init__(self, repo_file, master_config_file, token=None, workspace_dir="./workspace"):
        """Initialize the updater with the repository list file, master config template, and GitHub token."""
        self.repo_file = repo_file
        self.workspace_dir = workspace_dir
        self.master_config_file = master_config_file
        self.headers = {}
        
        # Use token from environment variable or passed parameter
        if token:
            self.token = token
        else:
            self.token = os.environ.get("GITHUB_TOKEN")
        
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
            logger.info("GitHub token configured successfully")
        else:
            logger.warning("No GitHub token provided. Private repositories won't be accessible.")
        
        # Create workspace directory if it doesn't exist
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Load CircleCI master config template from file
        self.master_config_template = self._load_master_config_template()
    
    def read_repositories(self):
        """Read the repository list from CSV file."""
        repos = []
        file_ext = Path(self.repo_file).suffix.lower()
        
        try:
            if file_ext == '.csv':
                with open(self.repo_file, 'r') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        repos.append({
                            'url': row['repository_url'],
                            'branch': row['branch']
                        })
            else:
                logger.error(f"Unsupported file format: {file_ext}")
                sys.exit(1)
                
            logger.info(f"Loaded {len(repos)} repositories from {self.repo_file}")
            return repos
            
        except Exception as e:
            logger.error(f"Error reading repository file: {e}")
            sys.exit(1)
    
    def clone_repository(self, repo_url, branch):
        """Clone or update a repository to the workspace directory."""
        # Extract repo name from URL
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        repo_path = os.path.join(self.workspace_dir, repo_name)
        
        try:
            if os.path.exists(repo_path):
                # Update existing repository
                logger.info(f"Updating existing repository: {repo_name}")
                repo = git.Repo(repo_path)
                origin = repo.remotes.origin
                origin.fetch()
                
                # Check if branch exists locally
                if branch in [ref.name.split('/')[-1] for ref in repo.references]:
                    repo.git.checkout(branch)
                else:
                    repo.git.checkout(f'origin/{branch}', b=branch)
                
                # Pull latest changes
                origin.pull()
            else:
                # Clone new repository
                logger.info(f"Cloning repository: {repo_name}, branch: {branch}")
                repo = git.Repo.clone_from(
                    repo_url, 
                    repo_path,
                    branch=branch
                )
            
            return repo_path
            
        except Exception as e:
            logger.error(f"Error handling repository {repo_name}: {e}")
            return None
    
    def detect_java_version(self, repo_path):
        """Detect Java version from build.gradle file."""
        gradle_file = os.path.join(repo_path, "build.gradle")
        
        # Check if build.gradle exists
        if not os.path.exists(gradle_file):
            logger.warning(f"build.gradle not found in {repo_path}")
            return None
        
        try:
            with open(gradle_file, 'r') as file:
                content = file.read()
                
                # Look for sourceCompatibility
                source_compat_match = re.search(r'sourceCompatibility\s*=\s*[\'"]?(\d+)[\'"]?', content)
                if source_compat_match:
                    version = source_compat_match.group(1)
                    logger.info(f"Detected Java version: {version}")
                    return version
                
                # Alternative pattern for JavaVersion.VERSION_*
                java_version_match = re.search(r'sourceCompatibility\s*=\s*JavaVersion\.VERSION_(\d+)', content)
                if java_version_match:
                    version = java_version_match.group(1)
                    logger.info(f"Detected Java version: {version}")
                    return version
                
                logger.warning("Could not detect Java version in build.gradle")
                return None
                
        except Exception as e:
            logger.error(f"Error reading build.gradle: {e}")
            return None
    
    def get_docker_image_for_java_version(self, java_version):
        """Return the appropriate Docker image for the given Java version."""
        try:
            java_version_int = int(java_version)
            
            if java_version_int >= 17:
                return "circleci/openjdk:17-buster-node-browsers-legacy"
            elif java_version_int >= 13:
                return "circleci/openjdk:13.0-buster-node-browsers-legacy"
            else:
                # Default to Java 13 image for lower versions
                logger.warning(f"No specific Docker image for Java {java_version}, using Java 13 image")
                return "circleci/openjdk:13.0-buster-node-browsers-legacy"
        except ValueError:
            logger.error(f"Invalid Java version: {java_version}")
            return "circleci/openjdk:13.0-buster-node-browsers-legacy"  # Default to Java 13 image
    
    def update_circleci_config(self, repo_path, java_version):
        """Update or create CircleCI config file based on Java version."""
        config_dir = os.path.join(repo_path, ".circleci")
        config_file = os.path.join(config_dir, "config.yml")
        
        # Create .circleci directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Get the appropriate Docker image for the Java version
        docker_image = self.get_docker_image_for_java_version(java_version)
        
        # Replace the placeholder in the template with the actual Docker image
        config_content = self.master_config_template.replace("{{JAVA_DOCKER_IMAGE}}", docker_image)
        
        try:
            # Write the config file
            with open(config_file, 'w') as file:
                file.write(config_content)
            
            logger.info(f"Updated CircleCI config for Java {java_version} with Docker image {docker_image} in {repo_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating CircleCI config: {e}")
            return False
    
    def commit_and_push_changes(self, repo_path, java_version):
        """Commit and push changes to the repository."""
        try:
            repo = git.Repo(repo_path)
            
            # Check if there are changes
            if not repo.is_dirty():
                logger.info("No changes to commit")
                return True
            
            # Add changes
            repo.git.add(".circleci/config.yml")
            
            # Commit changes
            commit_message = f"Update CircleCI config for Java {java_version}"
            repo.git.commit("-m", commit_message)
            
            # Push changes
            repo.git.push()
            
            logger.info(f"Changes committed and pushed: {commit_message}")
            return True
            
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False
    
    def process_repositories(self):
        """Process all repositories in the list."""
        repos = self.read_repositories()
        
        for repo in repos:
            repo_url = repo['url']
            branch = repo['branch']
            
            logger.info(f"Processing repository: {repo_url}, branch: {branch}")
            
            # Clone or update repository
            repo_path = self.clone_repository(repo_url, branch)
            if not repo_path:
                logger.error(f"Skipping {repo_url} due to clone error")
                continue
            
            # Detect Java version
            java_version = self.detect_java_version(repo_path)
            if not java_version:
                logger.warning(f"Skipping {repo_url} due to missing Java version")
                continue
            
            # Update CircleCI config
            if self.update_circleci_config(repo_path, java_version):
                # Commit and push changes
                self.commit_and_push_changes(repo_path, java_version)
    
    def _load_master_config_template(self):
        """Load CircleCI master config template from file."""
        try:
            # Load master template
            with open(self.master_config_file, 'r') as file:
                template = file.read()
                logger.info(f"Loaded master template from {self.master_config_file}")
            
            return template
            
        except Exception as e:
            logger.error(f"Error loading master config template: {e}")
            sys.exit(1)

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Update CircleCI configs based on Java version')
    parser.add_argument('repo_file', help='Path to repository list file (CSV or INI)')
    parser.add_argument('master_config', help='Path to master CircleCI config template file')
    parser.add_argument('--token', help='GitHub token')
    parser.add_argument('--workspace', default='./workspace', help='Workspace directory for cloned repositories')
    args = parser.parse_args()
    
    # Create updater and process repositories
    updater = JavaVersionConfigUpdater(
        args.repo_file, 
        args.master_config, 
        args.token, 
        args.workspace
    )
    updater.process_repositories()

if __name__ == "__main__":
    main()