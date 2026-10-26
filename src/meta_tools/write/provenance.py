"""Builds the provenance block (group 5 of the metadata model) for a YAML
config source file: source hash, git commit, and who/when it was written.
"""

from typing import Union
from pathlib import Path
import hashlib
import subprocess
import warnings
import pandas as pd

__all__ = ["get_yaml_provenance"]


def _get_git_commit(repo_root: Union[str, Path]) -> Union[str, None]:
    """
    Short hash of the current git HEAD.

    Parameters
    ----------
    repo_root : str or Path
        Path to the git repository root; passed as `cwd` to git.

    Returns
    -------
    str or None
        The short commit hash, or None if it can't be resolved (git not
        installed, `repo_root` not a git repo, etc.) - a warning is raised
        in that case instead of failing.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        warnings.warn(f'get_yaml_provenance: could not resolve git_commit ({e})', RuntimeWarning)
        return None


def get_yaml_provenance(
        source_file: Union[str, Path],
        source_folder: Union[str, Path],
        repo_root: Union[str, Path],
        repo: str,
        quality: str|None=None,
        encoding='utf-8',
        username: Union[str, None] = None,
        notes: str | None=None,
        add_git_commit: bool = True) -> dict:
    """
    Build the group 5 (``provenance``) block for a YAML config file.

    See meta_contract.yaml. Stamped by the writer at write time, never
    written by hand. ``writer_version`` is not included: `to_parquet`
    adds it when it writes the block.

    Parameters
    ----------
    source_file : str or Path
        Name (or relative path) of the YAML file, with or without the
        `.yaml` suffix - so a caller that already has its ETL name and
        config folder can pass them straight through instead of
        pre-joining an absolute path.
    source_folder : str or Path
        Directory containing `source_file`. Required: this function has no
        opinion on where config files live, that's the caller's job.
    repo_root : str or Path
        Path to the git repository root, used to resolve `git_commit`.
        Required for the same reason as `source_folder`.
    repo : str
        Repo identifier stamped into the output (free string, ADR-012).
    quality : str or None, default None
        Stored as given - one of the contract's ``provenance.quality``
        values (bronze/silver/gold), or None. Not validated here.
    encoding : str, default 'utf-8'
        Encoding used to read the YAML file.
    username : str or None, default None
        Stored as given, unresolved - the caller passes whatever username
        it already knows, or None (the contract declares it
        ``required: false``).
    notes : str or None, default None
        Free text relating the table to sibling outputs of the same run
        (ADR-008).
    add_git_commit : bool, default True
        Resolve ``git_commit`` from `repo_root`. False stamps it as None
        without calling git (e.g. a producer that does not run inside a
        repo, where the lookup would only warn).

    Returns
    -------
    dict
        repo, source_path (the relative source_file, not the resolved path
        used to open it), source_sha256 (hash of the verbatim file bytes),
        git_commit (best-effort, see Notes), written_at (local time, no
        timezone), source_yaml (the file's raw text), username, quality,
        notes.

    Notes
    -----
    Reads the YAML verbatim from disk rather than accepting an
    already-parsed dict from the caller: nothing upstream keeps the raw
    text around once parsed, so a hash/copy taken from the dict would miss
    any change to the file's actual bytes (comments, formatting) while
    claiming to be a content hash of it.

    git_commit is the current HEAD in repo_root, best-effort: if git isn't
    available or repo_root isn't a git repo, it's None and a warning is
    raised rather than failing the write (the contract declares it
    ``required: false``). It's the last commit, not necessarily what
    source_yaml/source_sha256 reflect if the file has uncommitted changes.
    """
    filepath = Path(source_folder) / Path(source_file).with_suffix('.yaml')
    source_bytes = filepath.read_bytes()
    source_yaml = source_bytes.decode(encoding)

    return {
        'repo': repo,
        'source_path': Path(source_file).with_suffix('.yaml').as_posix(),
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'git_commit': _get_git_commit(repo_root) if add_git_commit else None,
        'written_at': pd.Timestamp.now(),
        'source_yaml': source_yaml,
        'username': username,
        'quality': quality,
        'notes': notes
    }

