import subprocess
import sys
import os
import re
from pathlib import Path

import anthropic


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
        f"the calibration and synthesized data below.\n\n"
        f"For each file you create, output it in this exact format:\n"
        f"FILE: <filename>\n"
        f"```\n<file contents>\n```\n\n"
        f"Topic: {topic}\n"
        f"Calibration: {level_context}\n\n"
        f"Synthesized Data:\n{learning_data}"
    )


def write_files_from_response(response_text, target_dir):
    pattern = re.compile(r"FILE:\s*(\S+)\s*\n```[^\n]*\n(.*?)```", re.DOTALL)
    matches = pattern.findall(response_text)
    if not matches:
        print("[-] No FILE blocks found in response. Saving raw output as output.md")
        Path(target_dir, "output.md").write_text(response_text, encoding="utf-8")
        return

    for filename, contents in matches:
        file_path = Path(target_dir) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(contents, encoding="utf-8")
        print(f"[+] Created: {file_path}")


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

    print(f"\n[*] Sending calibrated prompt to Claude API...")

    api_key = None
    try:
        result = subprocess.run(['api-pilot', 'get', 'anthropic'], capture_output=True, text=True)
        if result.returncode == 0:
            api_key = result.stdout.strip()
    except FileNotFoundError:
        print("[-] Warning: api-pilot not found. Falling back to environment ANTHROPIC_API_KEY.")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8096,
        messages=[{"role": "user", "content": instruction}],
    )

    response_text = message.content[0].text
    print(f"[*] Tokens used — input: {message.usage.input_tokens}, output: {message.usage.output_tokens}")

    write_files_from_response(response_text, target_dir)
    print("[+] Done.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python claude_bridge.py <source_md_file> <target_project_dir>")
        sys.exit(1)

    run_claude_bridge(sys.argv[1], sys.argv[2])
