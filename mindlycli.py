#!/usr/bin/env python3
"""


"""
import sys

from mindly import MindlyCli

try:
    MindlyCli(sys.argv[1:])
    sys.exit(0)
except KeyboardInterrupt:
    sys.exit(1)
