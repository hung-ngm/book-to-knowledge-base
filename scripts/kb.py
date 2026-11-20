#!/usr/bin/env python3
"""Library commands: init, concepts, index, validate, relink, reader-skill, remove-book.

Run as a script, never `python -m book_to_kb...`: Python compiles a package's
__main__ before any of our code can turn bytecode off, which would leave
__pycache__ inside an installed skill.
"""

import os
import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from book_to_kb.library.cli import main

if __name__ == "__main__":
    sys.exit(main())
