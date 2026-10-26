"""Link the user's local folders for the scripts under ``scripts/``.

Its only job is to turn names into local paths: load the user's ``.env``
into the process environment, and resolve "env var name + optional
subfolder" into a `Path`. It does not read config files and does not check
that the paths exist.

How ``.env`` gets loaded:

- Which file: ``<repo root>/.env``, repo root = parent of ``scripts/``
  (`REPO_ROOT`, taken from this file's location, not the working
  directory). Template: ``.env.example``.
- When: only when a script calls `load_project_env`. Importing this module
  loads nothing.
- How / into what: python-dotenv ``load_dotenv`` copies each variable into
  ``os.environ`` of the current process (nothing is persisted).
- Precedence: a variable already in the environment wins over ``.env``
  (``override=False``).
- Missing file: not an error, nothing is loaded; `resolve_env` then raises
  for the first variable it cannot find.

`resolve_env` reads ``os.environ`` only, so `load_project_env` must run
first. Typical use::

    repo_root = load_project_env()         # <repo root>/.env -> os.environ
    out_dir = resolve_env("METADATAPATH")  # Path read from os.environ

Reading the ETL config is not its job: scripts resolve each ``path:`` node
with ``resolve_env(**path)`` and pass `resolve_env` as the resolver of
`meta_tools.etl.load_input_sources`, which discovers the ``input:`` tables.

Not part of the installable package: scripts import it as a sibling module
(``from project_env import ...``).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]  # parent of scripts/


def load_env(path: str | Path) -> None:
    """Load a ``.env`` file into ``os.environ`` via ``load_dotenv``.

    Uses python-dotenv; variables are set for the current process only. Variables already in the
    environment win (``override=False``). A missing file is not an error:
    nothing is loaded.

    Parameters
    ----------
    path : str or Path
        Location of the ``.env`` file.

    Returns
    -------
    None
    """
    load_dotenv(path, override=False)


def load_project_env() -> Path:
    """Load ``<repo root>/.env`` (``REPO_ROOT / ".env"``) into ``os.environ``.

    Same rules as `load_env`: existing variables win, a missing file loads
    nothing. Nothing is loaded at import time: scripts call this once at
    start, before `resolve_env`.

    Returns
    -------
    Path
        `REPO_ROOT`, so callers can locate repo files from it.
    """
    load_env(REPO_ROOT / ".env")
    return REPO_ROOT


def resolve_env(env: str, subfolder: str | Path | None = None) -> Path:
    """Turn an env var name plus an optional subfolder into a local path.

    Reads ``os.environ`` only, never the ``.env`` file: call
    `load_project_env` first so ``.env`` values are visible. The path is not
    checked for existence.

    Parameters
    ----------
    env : str
        Name of the environment variable holding the root folder.
    subfolder : str or Path or None, default None
        Subfolder appended to the root, if given.

    Returns
    -------
    Path
        The root, or ``root / subfolder`` when `subfolder` is given.

    Raises
    ------
    RuntimeError
        If `env` is unset or empty in ``os.environ``.
    """
    value = os.environ.get(env)
    if not value:
        raise RuntimeError(f"{env} is not set in .env or in the environment")
    root = Path(value)
    return root / subfolder if subfolder is not None else root
