"""Startup banner for the Apyra developer CLI.

The banner is cosmetic and must never interfere with automation:

* It renders only on interactive terminals (a TTY attached to stdout).
* It is disabled in CI, when ``APYRA_NO_BANNER`` is set, when ``--no-banner`` is
  passed, and when the command emits machine-readable JSON.
* Rich is optional; when unavailable the banner falls back to plain text.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from typing import TextIO

from apyra.core import __version__ as APYRA_VERSION

BANNER_ENV_VAR = "APYRA_NO_BANNER"
ENVIRONMENT_ENV_VAR = "APYRA_ENVIRONMENT"
DEFAULT_ENVIRONMENT = "development"

# Any truthy value in these variables indicates a CI system and disables the banner.
_CI_VARIABLES = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "CIRCLECI",
    "TRAVIS",
    "BUILDKITE",
    "TEAMCITY_VERSION",
    "JENKINS_URL",
)

# figlet "standard" rendering of the Apyra wordmark.
BANNER_ART = r"""    _    ____
   / \  |  _ \ _   _ _ __ __ _
  / _ \ | |_) | | | | '__/ _` |
 / ___ \|  __/| |_| | | | (_| |
/_/   \_\_|    \__, |_|  \__,_|
                |___/"""


def _is_truthy(value: str | None) -> bool:
    """Return True for common truthy environment-value spellings."""
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def is_ci(environ: Mapping[str, str]) -> bool:
    """Return True when the environment identifies a CI system."""
    return any(_is_truthy(environ.get(name)) for name in _CI_VARIABLES)


def _resolve_environment(environ: Mapping[str, str]) -> str:
    raw = environ.get(ENVIRONMENT_ENV_VAR, "").strip()
    return raw or DEFAULT_ENVIRONMENT


def should_show_banner(
    *,
    no_banner: bool = False,
    json_output: bool = False,
    is_terminal: bool | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return True when the startup banner should be rendered.

    The banner is suppressed by an explicit ``--no-banner`` flag, machine-readable
    JSON output, the ``APYRA_NO_BANNER`` environment variable, CI environments, and
    non-interactive (non-TTY) terminals.
    """
    if no_banner:
        return False
    if json_output:
        return False
    resolved_env = os.environ if environ is None else environ
    if _is_truthy(resolved_env.get(BANNER_ENV_VAR)):
        return False
    if is_ci(resolved_env):
        return False
    terminal = sys.stdout.isatty() if is_terminal is None else is_terminal
    return terminal


def _has_rich() -> bool:
    from importlib.util import find_spec

    return find_spec("rich") is not None


def _print_banner_rich(stream: TextIO, version: str, environment: str) -> None:
    from rich.console import Console
    from rich.text import Text

    console = Console(file=stream, highlight=False)
    art = Text(BANNER_ART)
    art.stylize("bold cyan")
    console.print(art)

    info = Text()
    info.append(f"Apyra {version}", style="bold")
    info.append("  ·  ", style="dim")
    info.append("environment: ", style="dim")
    info.append(environment, style="cyan")
    console.print(info)


def print_banner(
    *,
    version: str = APYRA_VERSION,
    environment: str | None = None,
    environ: Mapping[str, str] | None = None,
    stream: TextIO | None = None,
) -> None:
    """Render the startup banner to ``stream`` (stdout by default).

    Rich provides terminal colors when installed; otherwise the banner is printed
    as plain, uncolored text.
    """
    target = stream if stream is not None else sys.stdout
    resolved_env = os.environ if environ is None else environ
    resolved_environment = (
        environment if environment is not None else _resolve_environment(resolved_env)
    )

    if _has_rich():
        _print_banner_rich(target, version, resolved_environment)
        return

    target.write(BANNER_ART + "\n")
    target.write(f"Apyra {version} · environment: {resolved_environment}\n")
