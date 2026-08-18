# ai/prompt_builder.py

ALLOWED_ACTIONS = [
    "create_folder",
    "write_file",
    "read_file",
    "list_dir",
    "run_command",
    "install_pkg",
    "pip_install",
    "open_app",
    "open_file",
    "open_url"
]

SYSTEM_RULES = f"""
You are an Android AI Operator running inside Termux.

STRICT RULES:
- Respond ONLY with valid JSON
- Do NOT explain anything
- Do NOT include markdown
- Do NOT include comments
- Do NOT include shell commands directly

You may ONLY use these action types:
{ALLOWED_ACTIONS}

JSON FORMAT:
{{
  "actions": [
    {{
      "type": "action_type",
      "params": {{}}
    }}
  ]
}}
"""

class PromptBuilder:
    @staticmethod
    def build(user_input: str) -> str:
        return SYSTEM_RULES + "USER REQUEST:" + user_input
