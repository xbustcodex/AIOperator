"""Test suite for Buster OS."""

import sys

os_path = __import__("os").path

sys.path.insert(0, os_path.abspath(os_path.join(os_path.dirname(__file__), "..")))