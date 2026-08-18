# core/action_router.py
from ai.intent_parser import IntentParser
from core.validator import Validator
from executors import file_executor, termux_executor, app_executor

class ActionRouter:
    EXECUTOR_MAP = {
        "create_folder": file_executor.FileExecutor.create_folder,
        "write_file": lambda params: file_executor.FileExecutor.write_file(params.get("path",""), params.get("content","")),
        "read_file": lambda params: file_executor.FileExecutor.read_file(params.get("path","")),
        "list_dir": lambda params: file_executor.FileExecutor.list_dir(params.get("path","")),
        "run_command": lambda params: termux_executor.TermuxExecutor.run(params.get("command","")),
        "install_pkg": lambda params: termux_executor.TermuxExecutor.install(params.get("pkg","")),
        "pip_install": lambda params: termux_executor.TermuxExecutor.pip_install(params.get("pkg","")),
        "open_app": lambda params: app_executor.AppExecutor.open_app(params.get("package","")),
        "open_file": lambda params: app_executor.AppExecutor.open_file(params.get("path","")),
        "open_url": lambda params: app_executor.AppExecutor.open_url(params.get("url",""))
    }

    @staticmethod
    def route(json_str: str):
        actions = IntentParser.parse(json_str)
        results = []
        for action in actions:
            if Validator.validate_action(action):
                func = ActionRouter.EXECUTOR_MAP.get(action["type"])
                if func:
                    result = func(action.get("params", {}))
                    results.append({"action": action["type"], "result": result})
        return results
