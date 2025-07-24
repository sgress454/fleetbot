#!/usr/bin/env python3
"""
Script to process the supervisor template file and replace ${DIR} with the current directory.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    output_file = "supervisor.conf"
    
    # Get the directory where this script is located (should be the repo root)
    repo_dir = Path(__file__).parent.absolute()
    
    # Path to the template file
    template_path = repo_dir / ".supervisor_template"
    output_path = repo_dir / output_file
    
    # Check if template file exists
    if not template_path.exists():
        print(f"Error: Template file {template_path} not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Read the template file
        with open(template_path, 'r') as f:
            template_content = f.read()
        
        # Replace ${DIR} with the repository directory
        processed_content = template_content.replace('${DIR}', str(repo_dir))
        
        # Save to output file
        with open(output_path, 'w') as f:
            f.write(processed_content)
        
        print(f"Processed template saved to {output_path}")
        
    except Exception as e:
        print(f"Error processing template: {e}", file=sys.stderr)
        sys.exit(1)