#!/usr/bin/env python
"""Legacy shim: all packaging metadata lives in pyproject.toml.

VERSION is kept here because the stable-spec source-audit tool
(tools/audit_python_sdk.py in zenon-sdk-spec) reads it with a regex.
Keep it in sync with znn/__init__.py.
"""

from setuptools import setup

VERSION = "0.1.2"

setup()
