import subprocess
import sys
import os
from pathlib import Path


def assess_user_baseline(topic):
    print(f"\n[*] Calibrating complexity for: {topic}")
    print("[?] In one sentence, how would you approach the core architecture of this topic?")
    user_response = input("[>] Enter your approach (or type 'skip' if complete beginner): ")
    return user_response


def build_calibrated_prompt(topic, user_response, learning_data):
    if user_response.lower().strip() == 'skip':
        level_context = "The user is learning this from scratch. Start with core principles."
    else:
        level_context = (
            f"The user possesses this system-level understanding: '{user_response}'. "
            f"Bypass introductory concepts entirely. Align the generated project with this "
            f"structural logic and push their limits."
        )

    return (
        f"You are the Project Generator. Build a concrete, functional implementation based on "
        f"the calibration and synthesized data below. Save all relevant files directly in the "
        f"current directory.\n\n"
        f"Topic: {topic}\n"
        f"Calibration: {level_context}\n\n"
        f"Synthesized Data:\n{learning_data}"
    )


def run_claude_bridge(md_file_path, target_dir):
    if not os.path.exists(md_file_path):
        print(f"[-] Error: Source file {md_file_path} is missing.")
        sys.exit(1)

    Path(target_dir).mkdir(parents=True, exist_ok=True)

    with open(md_file_path, 'r', encoding='utf-8') as file:
        learning_data = file.read()

    topic = Path(md_file_path).stem

    user_response = assess_user_baseline(topic)
    instruction = build_calibrated_prompt(topic, user_response, learning_data)

    print(f"\n[*] Bridging data to Claude Code. Target directory: {target_dir}")

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
