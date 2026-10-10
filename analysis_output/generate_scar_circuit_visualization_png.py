"""Compatibility entry point; maintained implementation lives in experiments.legacy."""
import importlib as _importlib
import sys as _sys
from pathlib import Path as _Path
_root = str(_Path(__file__).resolve().parents[1])
if _root not in _sys.path:
    _sys.path.insert(0, _root)
_impl = _importlib.import_module("experiments.legacy.generate_scar_circuit_visualization_png")
globals().update({k: v for k, v in vars(_impl).items() if not k.startswith("__")})
if __name__ == "__main__":
    _impl.main()
