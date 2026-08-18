from executors.shell_executor import ShellExecutor
import os


class FileExecutor:

    @staticmethod
    def expand(path: str) -> str:
        return os.path.expanduser(path)


    @staticmethod
    def create_folder(path: str) -> str:
        path = FileExecutor.expand(path)
        return ShellExecutor.run(f"mkdir -p '{path}'")


    @staticmethod
    def write_file(path: str, content: str) -> str:
        path = FileExecutor.expand(path)

        safe = content.replace("'", "'\\''")

        cmd = f"echo '{safe}' > '{path}'"

        return ShellExecutor.run(cmd)


    @staticmethod
    def read_file(path: str) -> str:
        path = FileExecutor.expand(path)
        return ShellExecutor.run(f"cat '{path}'")


    @staticmethod
    def list_dir(path: str) -> str:
        path = FileExecutor.expand(path)
        return ShellExecutor.run(f"ls -la '{path}'")