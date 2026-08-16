"""
app/ml/__init__.py
Adds Naman's "Machine Learning" directory to sys.path and pre-loads
OR-Tools DLLs BEFORE XGBoost can claim zlib1.dll/abseil_dll.dll first.

On Windows, XGBoost and OR-Tools both ship their own zlib1.dll.
Whichever loads first "wins" — if XGBoost wins, OR-Tools DLL lookup
fails with WinError 127 ("procedure not found").
Loading OR-Tools here (at import time, before any ML inference code)
prevents the conflict.
"""
import sys
import pathlib

# ── 1. Add Naman's ML folder to sys.path ──────────────────────────
_ML_DIR = str(
    pathlib.Path(__file__).parents[2]
    / "SentinelAI-Intelligent-Public-Safety-Resource-Optimization-Platform"
    / "Machine Learning"
)
if _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)

# ── 2. Pre-load OR-Tools before XGBoost can claim shared DLLs ─────
try:
    from ortools.sat.python import cp_model as _cp  # noqa: F401
except Exception as _e:
    import warnings
    warnings.warn(f"OR-Tools pre-load failed: {_e}. Will use greedy fallback.")
