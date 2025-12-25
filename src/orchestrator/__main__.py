"""
Entry point for running the orchestrator as a module.

Usage:
    python -m src.orchestrator --once
    python -m src.orchestrator --config-dir config/agents
"""

from .main import main

if __name__ == "__main__":
    main()
