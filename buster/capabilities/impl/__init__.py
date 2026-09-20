"""Core capability implementations for Buster OS."""

from buster.capabilities.impl.android import AndroidCapability
from buster.capabilities.impl.filesystem import FileSystemCapability
from buster.capabilities.impl.git import GitCapability
from buster.capabilities.impl.network import NetworkCapability
from buster.capabilities.impl.process import ProcessCapability
from buster.capabilities.impl.python_runner import PythonRunnerCapability
from buster.capabilities.impl.shell import ShellCapability
from buster.capabilities.impl.terminal import TerminalCapability

CORE_CAPABILITIES = [
    FileSystemCapability,
    ShellCapability,
    TerminalCapability,
    PythonRunnerCapability,
    GitCapability,
    AndroidCapability,
    ProcessCapability,
    NetworkCapability,
]

__all__ = [
    "AndroidCapability",
    "CORE_CAPABILITIES",
    "FileSystemCapability",
    "GitCapability",
    "NetworkCapability",
    "ProcessCapability",
    "PythonRunnerCapability",
    "ShellCapability",
    "TerminalCapability",
]