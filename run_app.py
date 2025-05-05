#!/usr/bin/env python3
"""
Main entry point for the SLEEC Rules Analysis Pipeline.
"""
import os
import sys
import subprocess

def main():
    """Run the SLEEC Rules Analysis Pipeline application."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(current_dir, "src")
    pipeline_path = os.path.join(src_dir, "pipeline.py")
    
    # Make sure src directory is in Python path
    sys.path.append(src_dir)
    
    # Make sure required directories exist
    data_dir = os.path.join(current_dir, "data")
    rules_dir = os.path.join(data_dir, "rules")
    output_dir = os.path.join(data_dir, "output")
    traces_dir = os.path.join(output_dir, "traces")
    lts_dir = os.path.join(output_dir, "lts")
    
    os.makedirs(rules_dir, exist_ok=True)
    os.makedirs(traces_dir, exist_ok=True)
    os.makedirs(lts_dir, exist_ok=True)
    
    # Run the Streamlit application
    cmd = ["streamlit", "run", pipeline_path]
    
    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"Error running Streamlit app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 