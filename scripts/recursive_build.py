#!/usr/bin/env python3
"""Compatibility entrypoint for the recursive-build master.

Kept so existing callers of scripts/recursive_build.py continue to work.
"""
from __future__ import annotations

from Recursive_Build_Master import main

if __name__ == "__main__":
    raise SystemExit(main())
