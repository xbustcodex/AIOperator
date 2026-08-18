# executors/app_executor.py
from executors.shell_executor import ShellExecutor

class AppExecutor:
    @staticmethod
    def open_app(package: str) -> str:
        """Open an Android app by package name"""
        return ShellExecutor.run(
            f"monkey -p {package} -c android.intent.category.LAUNCHER 1"
        )

    @staticmethod
    def open_file(path: str) -> str:
        """Open a file using Android VIEW intent"""
        return ShellExecutor.run(
            f"am start -a android.intent.action.VIEW -d file://{path}"
        )

    @staticmethod
    def open_url(url: str) -> str:
        """Open a URL in the default browser"""
        return ShellExecutor.run(
            f"am start -a android.intent.action.VIEW -d '{url}'"
        )
