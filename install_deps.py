#!/usr/bin/env python3
"""
Dependency installation script for Lambda container builds.
Bypasses shell execution issues by using Python subprocess directly.
"""

import subprocess
import sys
import os

def main():
    # Set Lambda task root environment variable
    lambda_task_root = os.environ.get('LAMBDA_TASK_ROOT', '/var/task')
    
    print(f"Installing dependencies to: {lambda_task_root}")
    
    # Install dependencies using Python's pip module directly
    try:
        cmd = [
            sys.executable, '-m', 'pip', 'install', 
            '--no-cache-dir', '--target', lambda_task_root,
            '-r', '/tmp/requirements-docker.txt'
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        print("Dependencies installed successfully!")
        print("STDOUT:", result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
            
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
