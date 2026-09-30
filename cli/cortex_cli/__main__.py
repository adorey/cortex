"""``python -m cortex_cli`` — and the entry point PyInstaller builds the binary from.

PyInstaller runs this file as a script, outside its package: the import is absolute.
"""

import sys

from cortex_cli.main import main

if __name__ == "__main__":
    sys.exit(main())
