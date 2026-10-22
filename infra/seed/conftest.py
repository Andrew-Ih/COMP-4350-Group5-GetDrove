"""Lets the seed tests import the seed modules (infra/seed isn't a package)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
