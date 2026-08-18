#!/data/data/com.termux/files/usr/bin/python
# core/validator.py

"""
Action validation layer for AIOperator.

The LLM can suggest actions.
The Validator decides if those actions are allowed.
"""

import os


BLOCKED_PATHS = [
    "/system",
    "/vendor",
    "/data/adb",
    "/proc",
    "/dev",
]


DANGEROUS_COMMANDS = [
    "rm -rf",
    "rm -r",
    "dd ",
    "mkfs",
    "reboot",
    "shutdown",
    "poweroff",
    "chmod 777",
    "chown root",
]


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
    "open_url",
]


class Validator:

    @staticmethod
    def is_path_allowed(path: str) -> bool:
        """
        Check if a filesystem path is allowed.
        """

        if not path:
            return True

        path = os.path.expanduser(path)

        for blocked in BLOCKED_PATHS:
            if path.startswith(blocked):
                return False

        return True


    @staticmethod
    def is_command_safe(cmd: str) -> bool:
        """
        Check command against dangerous patterns.
        """

        if not cmd:
            return True

        command = cmd.lower()

        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                return False

        return True


    @staticmethod
    def is_action_allowed(action_type: str) -> bool:
        """
        Only allow known executor actions.
        """

        return action_type in ALLOWED_ACTIONS


    @staticmethod
    def validate_action(action: dict) -> bool:
        """
        Validate a single AI-generated action.
        """

        if not isinstance(action, dict):
            return False


        action_type = action.get("type")

        if not action_type:
            return False


        if not Validator.is_action_allowed(action_type):
            return False


        params = action.get("params", {})

        if not isinstance(params, dict):
            return False


        # Validate file paths

        path_fields = [
            "path",
            "file",
            "directory",
            "target",
        ]

        for field in path_fields:
            value = params.get(field)

            if value and not Validator.is_path_allowed(value):
                return False


        # Validate shell commands

        command = params.get("command")

        if command and not Validator.is_command_safe(command):
            return False


        return True


    @staticmethod
    def validate_actions(actions: list) -> list:
        """
        Filter a list of AI-generated actions.
        """

        valid = []

        for action in actions:

            if Validator.validate_action(action):
                valid.append(action)

        return valid