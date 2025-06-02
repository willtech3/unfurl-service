#!/usr/bin/env python3
"""
Deployment script for video proxy infrastructure.

This script handles the deployment of the video proxy Lambda function
and API Gateway infrastructure using AWS CDK.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
import requests


def run_command(command: str, description: str) -> str:
    """
    Run a shell command and return its output.

    Args:
        command: Shell command to execute
        description: Human-readable description of the command

    Returns:
        Command output as string

    Raises:
        SystemExit: If command fails
    """
    print(f" {description}...")
    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, check=True, timeout=300
        )
        print(f" {description} completed successfully")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f" {description} failed:")
        print(f"Command: {command}")
        print(f"Exit code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f" {description} timed out after 5 minutes")
        sys.exit(1)


def check_aws_credentials() -> None:
    """Check if AWS credentials are properly configured."""
    try:
        session = boto3.Session()
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        print(f" AWS credentials configured for account: {account_id}")
    except Exception as e:
        print(f" AWS credentials not configured: {e}")
        print("Please run 'aws configure' or set AWS environment variables")
        sys.exit(1)


def check_docker_running() -> None:
    """Check if Docker is running and accessible."""
    try:
        subprocess.run(
            ["docker", "version"], capture_output=True, check=True, timeout=10
        )
        print(" Docker is running and accessible")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        print(" Docker is not running or not accessible")
        print("Please start Docker and try again")
        sys.exit(1)


def install_dependencies() -> None:
    """Install required Python dependencies."""
    run_command("pip install -e .[cdk]", "Installing CDK dependencies")


def bootstrap_cdk() -> None:
    """Bootstrap CDK if not already done."""
    print(" Checking CDK bootstrap status...")
    try:
        # Try to list stacks to see if CDK is bootstrapped
        subprocess.run(["cdk", "list"], capture_output=True, check=True, timeout=60)
        print(" CDK already bootstrapped")
    except subprocess.CalledProcessError:
        print(" CDK not bootstrapped, bootstrapping now...")
        run_command("cdk bootstrap", "Bootstrapping CDK")


def synthesize_stack() -> None:
    """Synthesize the CDK stack to check for errors."""
    run_command("cdk synth", "Synthesizing CDK stack")


def deploy_stack() -> str:
    """
    Deploy the CDK stack and return the outputs.

    Returns:
        Stack outputs as JSON string
    """
    output = run_command("cdk deploy --require-approval never", "Deploying stack")

    # Extract outputs from CDK output
    # CDK outputs are typically at the end of the deployment output
    lines = output.split("\n")
    outputs_section = False
    outputs = {}

    for line in lines:
        if "Outputs:" in line:
            outputs_section = True
            continue
        elif outputs_section and "=" in line:
            # Parse output line like "UnfurlServiceStack.VideoProxyApiUrl = https://..."
            if "." in line:
                key_part = line.split("=")[0].strip()
                value_part = line.split("=")[1].strip()
                # Extract just the output name (after the dot)
                if "." in key_part:
                    output_name = key_part.split(".")[-1]
                    outputs[output_name] = value_part

    return json.dumps(outputs, indent=2)


def validate_deployment(outputs: str) -> None:
    """
    Validate that the deployment was successful.

    Args:
        outputs: Stack outputs as JSON string
    """
    try:
        outputs_dict = json.loads(outputs)

        # Check for required outputs
        required_outputs = ["VideoProxyApiUrl", "VideoProxyLambdaName"]
        for output in required_outputs:
            if output not in outputs_dict:
                print(f" Required output '{output}' not found in stack outputs")
                sys.exit(1)

        api_url = outputs_dict.get("VideoProxyApiUrl")
        lambda_name = outputs_dict.get("VideoProxyLambdaName")

        print(f" Video Proxy API URL: {api_url}")
        print(f" Video Proxy Lambda Name: {lambda_name}")

        # Test API Gateway endpoint
        print(" Testing API Gateway endpoint...")

        try:
            response = requests.get(f"{api_url}/health", timeout=30)
            if response.status_code == 200:
                print(" API Gateway endpoint is responding")
            else:
                print(
                    f"  API Gateway endpoint returned status: "
                    f"{response.status_code}"
                )
        except requests.RequestException as e:
            print(f"  Could not test API Gateway endpoint: {e}")

    except json.JSONDecodeError:
        print(" Invalid JSON in stack outputs")
        sys.exit(1)


def update_environment_variables(outputs: str) -> None:
    """
    Update environment variables or configuration files with deployment outputs.

    Args:
        outputs: Stack outputs as JSON string
    """
    try:
        outputs_dict = json.loads(outputs)
        api_url = outputs_dict.get("VideoProxyApiUrl")

        if api_url:
            # Create or update .env file
            env_file = Path(".env")
            env_content = ""

            if env_file.exists():
                env_content = env_file.read_text()

            # Update or add VIDEO_PROXY_BASE_URL
            lines = env_content.split("\n")
            updated = False

            for i, line in enumerate(lines):
                if line.startswith("VIDEO_PROXY_BASE_URL="):
                    lines[i] = f"VIDEO_PROXY_BASE_URL={api_url}"
                    updated = True
                    break

            if not updated:
                lines.append(f"VIDEO_PROXY_BASE_URL={api_url}")

            env_file.write_text("\n".join(lines))
            print(f" Updated .env file with VIDEO_PROXY_BASE_URL={api_url}")

    except json.JSONDecodeError:
        print(" Invalid JSON in stack outputs")


def main_deploy() -> None:
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy Instagram video proxy to AWS")
    parser.add_argument(
        "--environment", default="dev", help="Deployment environment (default: dev)",
    )

    parser.parse_args()

    print(" Starting video proxy deployment...")
    print("=" * 50)

    # Pre-deployment checks
    check_aws_credentials()
    check_docker_running()

    # Change to CDK directory
    original_dir = Path.cwd()
    cdk_dir = Path("cdk")

    if not cdk_dir.exists():
        print(" CDK directory not found")
        sys.exit(1)

    try:
        # Change to CDK directory for deployment
        os.chdir(cdk_dir)

        # Installation and setup
        install_dependencies()
        bootstrap_cdk()

        # Deployment
        synthesize_stack()
        outputs = deploy_stack()

        # Post-deployment validation
        validate_deployment(outputs)

        # Change back to original directory for env file update
        os.chdir(original_dir)
        update_environment_variables(outputs)

        print("\n" + "=" * 50)
        print(" Video proxy deployment completed successfully!")
        print("\nNext steps:")
        print("1. Update your Slack app OAuth scopes to include 'links:embed:write'")
        print("2. Add the API Gateway domain to your Slack app unfurl domains")
        print("3. Test video unfurls in a Slack channel")

    except Exception as e:
        print(f" Deployment failed: {e}")
        sys.exit(1)
    finally:
        # Always change back to original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    import argparse

    main_deploy()
