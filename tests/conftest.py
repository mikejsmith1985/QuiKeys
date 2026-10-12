"""Test setup: makes the src/ modules importable the same way the app imports them."""

import os
import sys

SOURCE_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SOURCE_DIRECTORY)
