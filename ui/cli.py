# ui/cli.py
import sys
import os
import re
import json
import subprocess
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import Agent
from services.logger import Logger
from core.action_router import ActionRouter

# Risky actions to run with tsu if admin
RISKY_ACTIONS = [
    "run_command",
    "install_pkg",
    "pip_install",
    "open_app",
    "open_file",
    "open_url"
]

# Admin/autonomous mode
ADMIN_MODE = True  # True = execute risky actions automatically as root

def run_with_tsu(command: str):
    """Run a shell command with root privileges"""
    try:
        full_command = f"tsu -c \"{command}\"" if ADMIN_MODE else command
        result = subprocess.check_output(full_command, shell=True, stderr=subprocess.STDOUT)
        return result.decode().strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.output.decode().strip()}"

def execute_json_actions(response_text):
    """Extract JSON actions from AI response and execute them"""
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if not json_match:
        return None, "No JSON found"

    try:
        action_json = json.loads(json_match.group())
        executed_results = []

        for action in action_json.get("actions", []):
            action_type = action["type"]
            params = action.get("params", {})

            # Auto-run risky actions with tsu in admin mode
            if action_type in ["run_command", "install_pkg", "pip_install"]:
                cmd = params.get("command") or params.get("pkg")
                result = run_with_tsu(cmd)
            else:
                func = ActionRouter.EXECUTOR_MAP.get(action_type, lambda p: "Unknown action")
                result = func(params)

            executed_results.append({"action": action_type, "result": result})

        return action_json, executed_results

    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {str(e)[:100]}"
    except Exception as e:
        return None, f"Execution error: {str(e)}"

def main():
    print("=== AI Operator CLI (Autonomous Mode) ===")
    Logger.log("CLI started")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                Logger.log("CLI exited by user")
                print("Goodbye!")
                break

            if not user_input:
                continue

            print("🤖 Thinking...")
            results = Agent.run(user_input)

            # Extract AI response
            if isinstance(results, dict) and "ai_response" in results:
                ai_response = results["ai_response"]
            elif isinstance(results, str):
                ai_response = results
            elif isinstance(results, list):
                ai_response = "\n".join(str(r) for r in results)
            else:
                ai_response = str(results)

            # Execute JSON actions automatically
            json_data, action_results = execute_json_actions(ai_response)

            if isinstance(action_results, list):
                print("\n✅ Executed Actions:")
                for r in action_results:
                    print(f"- {r['action']}: {r['result']}")
            else:
                print(f"\n🤖 AI: {ai_response}")

    except KeyboardInterrupt:
        Logger.log("CLI interrupted")
        print("\nExiting...")
    except Exception as e:
        Logger.log(f"CLI error: {e}")
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()