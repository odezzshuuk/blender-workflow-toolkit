"""Load standalone scripts from the repository's runtime/headless directories."""

import importlib.util
from pathlib import Path
import sys


def load_script(directory, name):
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / directory / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]
