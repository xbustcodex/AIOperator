"""Core capability implementations for Buster OS."""

from buster.capabilities.impl.android import AndroidCapability
from buster.capabilities.impl.archive import ArchiveCapability
from buster.capabilities.impl.crypto import CryptoCapability
from buster.capabilities.impl.filesystem import FileSystemCapability
from buster.capabilities.impl.git import GitCapability
from buster.capabilities.impl.network import NetworkCapability
from buster.capabilities.impl.pkg import PackageCapability
from buster.capabilities.impl.process import ProcessCapability
from buster.capabilities.impl.python_runner import PythonRunnerCapability
from buster.capabilities.impl.search import SearchCapability
from buster.capabilities.impl.shell import ShellCapability
from buster.capabilities.impl.terminal import TerminalCapability
from buster.capabilities.impl.time_utils import TimeCapability

CORE_CAPABILITIES = [
    FileSystemCapability,
    ShellCapability,
    TerminalCapability,
    PythonRunnerCapability,
    GitCapability,
    AndroidCapability,
    ProcessCapability,
    NetworkCapability,
    SearchCapability,
    ArchiveCapability,
    CryptoCapability,
    TimeCapability,
    PackageCapability,
]

__all__ = [
    "AndroidCapability",
    "ArchiveCapability",
    "CORE_CAPABILITIES",
    "CryptoCapability",
    "FileSystemCapability",
    "GitCapability",
    "NetworkCapability",
    "PackageCapability",
    "ProcessCapability",
    "PythonRunnerCapability",
    "SearchCapability",
    "ShellCapability",
    "TerminalCapability",
    "TimeCapability",
]