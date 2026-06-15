"""Shared test setup: make the scripts in ``hamip.at/`` importable.

The application modules live in the ``hamip.at/`` directory (not a package),
so the tests add that directory to ``sys.path``.
"""
import os
import sys

HAMIP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hamip.at")
if HAMIP_DIR not in sys.path:
    sys.path.insert(0, HAMIP_DIR)
