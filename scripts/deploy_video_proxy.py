#!/usr/bin/env python3
"""
Deployment script for Instagram video proxy functionality.

This script deploys the video proxy feature and validates the deployment.
"""

import subprocess
import sys
import json
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional


class VideoProxyDeployer:
    """Handles deployment of video proxy functionality."""

    def __init__(self, environment: str = "dev", region: str = "us-east-2"):
        """Initialize deployer."""
        self.environment = environment
        self.region = region
        self.project_root = Path(__file__).parent.parent
        
    def deploy(self) -> bool:
        """Deploy video proxy functionality."""
        print(f"🚀 Deploying Instagram Video Proxy - {self.environment}")
        print("=" * 60)
        
        # Step 1: Pre-deployment validation
        if not self._pre_deployment_checks():
            return False
        
        # Step 2: Run tests
        if not self._run_tests():
            return False
        
        # Step 3: Deploy CDK stack
        if not self._deploy_cdk_stack():
            return False
        
        # Step 4: Wait for deployment to stabilize
        if not self._wait_for_stabilization():
            return False
        
        # Step 5: Post-deployment validation
        api_url = self._get_api_gateway_url()
        if not api_url:
            print("❌ Could not retrieve API Gateway URL")
            return False
            
        if not self._validate_deployment(api_url):
            print("❌ Post-deployment validation failed")
            return False
        
        # Step 6: Display next steps
        self._display_next_steps(api_url)
        
        return True

    def _pre_deployment_checks(self) -> bool:
        """Run pre-deployment validation checks."""
        print("\n🔍 Pre-deployment validation")
        print("-" * 40)
        
        checks = [
            ("UV installed", self._check_uv),
            ("AWS credentials", self._check_aws_credentials),
            ("CDK bootstrap", self._check_cdk_bootstrap),
            ("Dependencies installed", self._check_dependencies),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            if check_func():
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
                all_passed = False
        
        return all_passed

    def _check_uv(self) -> bool:
        """Check if UV is installed."""
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_aws_credentials(self) -> bool:
        """Check AWS credentials."""
        try:
            result = subprocess.run(
                ["aws", "sts", "get-caller-identity"],
                capture_output=True,
                check=True,
                text=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_cdk_bootstrap(self) -> bool:
        """Check CDK bootstrap status."""
        try:
            result = subprocess.run(
                ["cdk", "bootstrap", "--show-template"],
                capture_output=True,
                cwd=self.project_root
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_dependencies(self) -> bool:
        """Check if dependencies are installed."""
        try:
            subprocess.run(
                ["uv", "run", "python", "-c", "import boto3, requests"],
                capture_output=True,
                check=True,
                cwd=self.project_root
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _run_tests(self) -> bool:
        """Run video proxy tests."""
        print("\n🧪 Running tests")
        print("-" * 40)
        
        try:
            result = subprocess.run(
                ["python", "scripts/run_video_tests.py"],
                cwd=self.project_root,
                timeout=300
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("❌ Tests timed out")
            return False
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return False

    def _deploy_cdk_stack(self) -> bool:
        """Deploy CDK stack."""
        print("\n🏗️  Deploying CDK stack")
        print("-" * 40)
        
        try:
            cmd = [
                "cdk", "deploy",
                f"unfurl-service-{self.environment}",
                "--require-approval", "never",
                "--progress", "events"
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                timeout=1800  # 30 minutes
            )
            
            if result.returncode == 0:
                print("✅ CDK deployment completed successfully")
                return True
            else:
                print(f"❌ CDK deployment failed (exit code: {result.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ CDK deployment timed out")
            return False
        except Exception as e:
            print(f"❌ CDK deployment error: {e}")
            return False

    def _wait_for_stabilization(self) -> bool:
        """Wait for deployment to stabilize."""
        print("\n⏳ Waiting for deployment stabilization")
        print("-" * 40)
        
        # Wait 30 seconds for Lambda functions to be ready
        for i in range(30):
            print(f"Waiting... {i+1}/30 seconds", end="\r")
            time.sleep(1)
        
        print("\n✅ Stabilization complete")
        return True

    def _get_api_gateway_url(self) -> Optional[str]:
        """Get API Gateway URL from CDK outputs."""
        print("\n🔗 Retrieving API Gateway URL")
        print("-" * 40)
        
        try:
            result = subprocess.run(
                ["aws", "cloudformation", "describe-stacks",
                 "--stack-name", f"unfurl-service-{self.environment}",
                 "--region", self.region],
                capture_output=True,
                text=True,
                check=True
            )
            
            stacks_data = json.loads(result.stdout)
            stacks = stacks_data.get("Stacks", [])
            
            if not stacks:
                print("❌ Stack not found")
                return None
            
            outputs = stacks[0].get("Outputs", [])
            for output in outputs:
                if output.get("OutputKey") == "ApiGatewayUrl":
                    url = output.get("OutputValue")
                    print(f"✅ API Gateway URL: {url}")
                    return url
            
            print("❌ API Gateway URL not found in stack outputs")
            return None
            
        except Exception as e:
            print(f"❌ Failed to get API Gateway URL: {e}")
            return None

    def _validate_deployment(self, api_url: str) -> bool:
        """Validate deployment using validation script."""
        print("\n✅ Running post-deployment validation")
        print("-" * 40)
        
        try:
            cmd = [
                "python", "scripts/validate_video_deployment.py",
                "--api-url", api_url,
                "--environment", self.environment
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                timeout=180  # 3 minutes
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("❌ Validation timed out")
            return False
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False

    def _display_next_steps(self, api_url: str) -> None:
        """Display next steps for completing setup."""
        print("\n🎉 DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        print("\n📋 NEXT STEPS:")
        print("-" * 40)
        
        print("1. 🔐 Update Slack App OAuth Scopes:")
        print("   - Go to https://api.slack.com/apps")
        print("   - Add 'links:embed:write' scope (Bot + User)")
        print("   - Reinstall app to workspace")
        
        print("\n2. 🌐 Configure Unfurl Domains:")
        domain = api_url.replace("https://", "").replace("http://", "").split("/")[0]
        print(f"   - Add domain: {domain}")
        print("   - In Slack app Event Subscriptions > App Unfurl Domains")
        
        print("\n3. 🔑 Update Bot Token:")
        print("   - Copy new Bot User OAuth Token after reinstall")
        print(f"   - Update AWS Secrets Manager secret: unfurl-service-slack-credentials-{self.environment}")
        
        print("\n4. 🧪 Test Video Playback:")
        print("   - Share Instagram video link in Slack")
        print("   - Verify embedded video player appears")
        print("   - Test video playback functionality")
        
        print("\n5. 📊 Monitor Performance:")
        print("   - CloudWatch logs: /aws/lambda/video-proxy-{self.environment}")
        print("   - DynamoDB metrics for cache performance")
        
        print(f"\n📄 Setup guide: {self.project_root}/SLACK_VIDEO_SETUP.md")
        print(f"🔗 API URL: {api_url}")


def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy video proxy functionality")
    parser.add_argument(
        "--environment",
        default="dev",
        help="Environment to deploy to (default: dev)"
    )
    parser.add_argument(
        "--region",
        default="us-east-2",
        help="AWS region (default: us-east-2)"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests before deployment"
    )
    
    args = parser.parse_args()
    
    deployer = VideoProxyDeployer(args.environment, args.region)
    
    if args.skip_tests:
        deployer._run_tests = lambda: True  # Skip tests
    
    success = deployer.deploy()
    
    if success:
        print("\n🚀 Video proxy deployment completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Video proxy deployment failed!")
        print("🔧 Check errors above and retry deployment.")
        sys.exit(1)


if __name__ == "__main__":
    main()
