import subprocess
import sys
import os
from pathlib import Path


def run_claude_bridge(md_file_path, target_dir):
    if not os.path.exists(md_file_path):
        print(f"[-] Error: Source file {md_file_path} is missing.")
        sys.exit(1)

    Path(target_dir).mkdir(parents=True, exist_ok=True)

    with open(md_file_path, 'r', encoding='utf-8') as file:
        learning_data = file.read()

    instruction = (
        f"You are the Project Generator. Read the following synthesized data and build a concrete, "
        f"functional implementation. Save all relevant files directly in the current directory.\n\n"
        f"Data:\n{learning_data}"
    )

    print(f"[*] Bridging data to Claude Code. Target directory: {target_dir}")

    # Fetch API key via api-pilot if available
    try:
        api_key_process = subprocess.run(
            ['api-pilot', 'get', 'anthropic'],
            capture_output=True,
            text=True
        )
        if api_key_process.returncode == 0:
            os.environ['ANTHROPIC_API_KEY'] = api_key_process.stdout.strip()
        else:
            print("[-] Warning: api-pilot returned an error. Falling back to environment ANTHROPIC_API_KEY.")
    except FileNotFoundError:
        print("[-] Warning: api-pilot not found. Falling back to environment ANTHROPIC_API_KEY.")

    try:
        subprocess.run(["claude", instruction], cwd=target_dir)
        print("[+] Claude Code execution completed.")
    except FileNotFoundError:
        print("[-] Error: 'claude' command not found. Verify @anthropic-ai/claude-code is installed globally.")
    except Exception as e:
        print(f"[-] Execution failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python claude_bridge.py <source_md_file> <target_project_dir>")
        sys.exit(1)

    run_claude_bridge(sys.argv[1], sys.argv[2])
