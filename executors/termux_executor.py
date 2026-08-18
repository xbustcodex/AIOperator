# executors/termux_executor.py
from executors.shell_executor import ShellExecutor

class TermuxExecutor:
    @staticmethod
    def run(command: str) -> str:
        """Run a command inside Termux environment"""
        return ShellExecutor.run(command)

    @staticmethod
    def install(pkg: str) -> str:
        return ShellExecutor.run(f"pkg install -y {pkg}")

    @staticmethod
    def pip_install(pkg: str) -> str:
        return ShellExecutor.run(f"pip install {pkg}")
