# executors/shell_executor.py
import subprocess

class ShellExecutor:
    @staticmethod
    def run(cmd: str) -> str:
        """Run a shell command and return output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.stderr:
                return result.stderr.strip()
            return result.stdout.strip()
        except Exception as e:
            return str(e)
