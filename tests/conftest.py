import sys

# ParametersManager parses the CLI arguments on first use: provide a neutral action for unit tests
sys.argv = ["mandalore", "version"]

# Load every Command subclass before ParametersManager is first instantiated (as MandaloreController does)
import mandalore.console.cli.actions.MandaloreParameters  # noqa: E402,F401
