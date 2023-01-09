"""Get information about a repository using Git."""

import contextlib
import re
from typing import Generator

import git
from git.objects import Commit


def get_main_branch(repo: git.Repo) -> str:
    """Get the remote main branch name.

    Assumes that the remote is called ``"origin"``.

    :param repo: The Git repository to use
    :return: The name of the remote main branch, e.g. ``"origin/main"``
    :raises RuntimeError: if ``git ls-remote --symref origin HEAD`` fails

    """
    symref_output = repo.git.ls_remote("--symref", "origin", "HEAD")
    match = re.match(r"ref: refs/heads/(.+)\tHEAD\b", symref_output)
    if not match:
        raise RuntimeError(
            "Can't parse `git ls-remote --symref origin HEAD` output {symref_output!r}"
        )
    head = match.group(1)
    return f"origin/{head}"


def get_commit_list(
    repo: git.Repo, main_branch: str, local_branch: git.Head
) -> list[Commit]:
    """Get the list of commits between the main branch and the given feature branch.

    :param repo: The Git repository to use
    :param main_branch: The remote main branch, e.g. ``"origin/main"``
    :param local_branch: The local branch whose commits to look at
    :return: All the commits starting from the main branch

    """
    # On a branch, get the base commit which is in the main branch
    # (e.g. origin/master).
    base_commit = repo.merge_base(main_branch, local_branch)[0]
    return list(reversed(list(repo.iter_commits(f"{base_commit}..{local_branch}"))))


@contextlib.contextmanager
def in_tmp_branch(
    repo: git.Repo, name: str, commit: Commit
) -> Generator[git.Head, None, None]:
    """Create a temporary branch at the given commit, run code, and clean up.

    :param repo: The Git repository to use
    :param commit: The commit to create the temporary branch at
    :raises git.GitCommandError: if Git fails
    :yield: The temporary branch object

    """
    prev_active_branch = repo.active_branch
    tmp_branch = repo.create_head(name, commit.hexsha, force=True)
    repo.git.checkout(tmp_branch)
    try:
        yield tmp_branch
    except git.GitCommandError:
        print("Git exception occurred. Current git status:")
        print(repo.git.status())
        raise
    finally:
        repo.git.reset("--hard")
        repo.git.checkout(prev_active_branch)
        repo.delete_head(name, force=True)


def count_changed_lines_since(repo: git.Repo, commit0: Commit) -> int:
    """Find out the number of inserted/deleted lines since the given commit.

    :param repo: The Git repository to use
    :param commit0: The old commit to compare to
    :return: The total number of inserted and deleted lines

    """
    diff_str = repo.git.diff("--shortstat", f"{commit0}..HEAD")
    return get_shortstat_total(diff_str)


SHORTSTAT_RE = re.compile(
    r"""
    _ \d+ _ file s? _ changed
    (?: , _ (\d+) _ insertion s? \( \+ \) )?
    (?: , _ (\d+) _  deletion s? \(  - \) )?
    """.replace(
        "_", r"\ "
    ),
    re.VERBOSE,
)


def get_shortstat_total(shortstat_output: str) -> int:
    """Parse total insertions and deletions in ``git --shortstat``.

    >>> _get_shortstat_total(" 2 files changed, 1 insertion(+), 5 deletions(-)")
    6
    >>> _get_shortstat_total(" 1 file changed, 3 insertions(+)")
    3
    >>> _get_shortstat_total(" 2 files changed, 1 deletion(-)")
    1

    :param shortstat_output: Output from ``git diff --shortstat <commit>..<commit>`` or
                             ``git show --shortstat --format= <object>``
    :return: The sum of numbers of insertions and deletions
    :raises RuntimeError: if Git output doesn't match what's expected

    """
    match = SHORTSTAT_RE.match(shortstat_output)
    if not match:
        raise RuntimeError("Can't parse git --shortstat output {shortstat_output!r}")
    return int(match.group(1) or 0) + int(match.group(2) or 0)
