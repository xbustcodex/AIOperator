#!/data/data/com.termux/files/usr/bin/python
# ai/intent_parser.py

import json
import re


class IntentParser:

    @staticmethod
    def parse(json_str: str) -> list:
        """Parse AI JSON safely and return list of actions"""

        try:
            # Try normal JSON first
            data = json.loads(json_str)

        except json.JSONDecodeError:

            # Extract JSON object if model added extra text
            match = re.search(
                r"\{.*\}",
                json_str,
                re.DOTALL
            )

            if not match:
                return []

            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return []

        actions = data.get("actions", [])

        if not isinstance(actions, list):
            return []

        valid_actions = []

        for action in actions:
            if (
                isinstance(action, dict)
                and "type" in action
            ):
                if "params" not in action:
                    action["params"] = {}

                valid_actions.append(action)

        return valid_actions