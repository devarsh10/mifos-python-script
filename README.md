# Java Version Config Updater - Installation and Usage Guide

## Prerequisites
- Python 3.6 or higher
- Git installed and configured
- GitHub access token (for private repositories)

## Installation

1. Clone this repository

2. Create the virtual environment to avoid the 'Module not found error' 
using command `python -m venv venv`

3. If on windows: venv\Scripts\activate => On macOS/Linux: source venv/bin/activate

4. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Make the script executable:
   ```
   chmod +x java_version_config_updater.py
   ```

## Configuration

### GitHub Token Setup
For accessing private repositories or to avoid GitHub API rate limits, set up a GitHub token:

1. Create a token at GitHub: Settings > Developer settings > Personal access tokens
2. Give it the `repo` scope
3. Set the token as an environment variable:
   ```
   export GITHUB_TOKEN=your_token_here
   ```
   
   Or pass it directly to the script with the `--token` parameter.

### Repository List

Create one of the following files:

#### CSV Format (repositories.csv)
```
repository_url,branch
https://github.com/your-org/repo1,main
https://github.com/your-org/repo2,develop
```

## Usage

Run the script by providing the path to your repository list file and the config template files:

```
./java_version_config_updater.py repositories.csv master_config.yml
```

With a custom workspace directory:

```
./java_version_config_updater.py repositories.csv master_config.yml --workspace /path/to/workspace
```

With a GitHub token specified directly:

```
./java_version_config_updater.py repositories.csv master_config.yml --token your_github_token
```

## How It Works

1. The script reads the repository list from the CSV/INI file
2. For each repository:
   - Clones or updates the repository to the workspace directory
   - Detects the Java version from the build.gradle file by reading the sourceCompatibility value
   - Selects the appropriate CircleCI config template based on the Java version:
     - For Java 17 and higher or Java 13-16: modify this -> `- image: {{JAVA_DOCKER_IMAGE}}` accordingly
   - Updates the .circleci/config.yml file with the selected template
   - Commits and pushes the changes to the repository

## Logs

The script logs its actions to both the console and a log file named `config_updater.log` in the current directory.

## Troubleshooting

- **Authentication Issues**: Ensure your GitHub token has the correct permissions
- **Java Version Not Detected**: Check that the build.gradle file contains a sourceCompatibility setting
- **Push Failures**: Verify that you have write access to the repository