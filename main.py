"""
main.py — VivaLens AI (Entry Point)
===================================
Launcher for the VivaLens AI Streamlit application.

Usage:
    python main.py
    (equivalent to: streamlit run app.py)

If Streamlit is missing, prints install instructions instead of crashing.
"""

import subprocess
import sys
from pathlib import Path

# Resolve app.py relative to THIS file so the launcher works from any cwd.
APP_FILE = Path(__file__).resolve().parent / "app.py"
REQUIREMENTS = Path(__file__).resolve().parent / "requirements.txt"


def _print_install_help() -> None:
    """CLI fallback: print actionable install instructions."""
    print("=" * 60)
    print("  VivaLens AI — Streamlit is not installed.")
    print("=" * 60)
    print("Install all dependencies with:")
    print(f"    {sys.executable} -m pip install -r {REQUIREMENTS}")
    print()
    print("Or install just the UI framework:")
    print(f"    {sys.executable} -m pip install streamlit==1.41.1")
    print()
    print("Then run again:")
    print(f"    {sys.executable} {Path(__file__).name}")
    print("=" * 60)


def main() -> int:
    """Launch the Streamlit app. Returns a process exit code."""
    # --- Dependency check (CLI fallback) ---
    try:
        import streamlit  # noqa: F401
    except ImportError:
        _print_install_help()
        return 1

    # --- File check ---
    if not APP_FILE.is_file():
        print(f"ERROR: app.py not found at:\n  {APP_FILE}")
        return 1

    # --- Launch ---
    # --server.headless true: skips Streamlit's interactive email onboarding
    # prompt (which otherwise blocks the launcher waiting for stdin).
    # The local URL is printed below for the user to open.
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(APP_FILE),
        "--server.headless", "true",
        "--server.port", "8501",
        "--browser.gatherUsageStats", "false",
    ]
    print("Starting VivaLens AI ...")
    print("Open: http://localhost:8501  (press Ctrl+C to stop)")
    try:
        completed = subprocess.run(cmd, cwd=str(APP_FILE.parent))
        return completed.returncode
    except KeyboardInterrupt:
        print("\nVivaLens AI stopped by user.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
