#!/usr/bin/env python3
"""Extract clean text and chapter ranges from one or more book files."""

import os
import sys

# Keep __pycache__ out of an installed skill. Set before importing book_to_kb.
if __name__ == "__main__":
    sys.dont_write_bytecode = True

# Force UTF-8 output so Windows consoles on a legacy code page do not fail.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Import book_to_kb from the skill folder, whatever the working directory.
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from book_to_kb.cli import main

if __name__ == "__main__":
    main()
