"""Module entry point so ``python -m wiki_agent_harness`` works."""
from .cli import main
import sys

sys.exit(main())
