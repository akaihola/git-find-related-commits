#!/usr/bin/env python3

"""Find closely related commits in a Git branch

Copyright (c) 2023 Albert Zeyer, Antti Kaihola
Licensed under the MIT license. For details, see the file ``LICENSE`` in the root of the
repository at https://github.com/akaihola/git-find-related-commits

Adapted from https://github.com/albertz/helpers/blob/master/git-find-related-commits.py

https://stackoverflow.com/questions/66731069/find-pairs-of-most-related-commits
https://www.reddit.com/r/learnprogramming/comments/pftenx/cleanup_pr_lots_of_commits/

"""

from __future__ import annotations

import contextlib
import re
import sys
from typing import Generator, Iterable

import git  # pip install GitPython

_TmpBranchName = "tmp-find-related-commits"


class GitHelper:
    def __init__(self, repo_dir: str):
        self.repo = git.Repo(repo_dir)

        # get the main branch name
        symref_output = self.repo.git.ls_remote("--symref", "origin", "HEAD")
        match = re.match(r"ref: refs/heads/(.+)\tHEAD\b", symref_output)
        if not match:
            raise RuntimeError(
                "Can't parse `git --symref origin HEAD` output {symref_output!r}"
            )
        head = match.group(1)
        self.main_branch = f"origin/{head}"

        self.local_branch = self.repo.active_branch
        assert self.local_branch.name != _TmpBranchName

    def get_commit_list(self) -> list[git.Commit]:
        """
        Returns:
        All the commits starting from the main branch.
        """
        # On a branch, get the base commit which is in the main branch
        # (e.g. origin/master).
        base_commit = self.repo.merge_base(self.main_branch, self.local_branch)[0]
        return list(
            reversed(
                list(self.repo.iter_commits(f"{base_commit}..{self.local_branch}"))
            )
        )

    def count_changed_lines_since(self, commit0: git.Commit) -> int:
        diff_str = self.repo.git.diff("--shortstat", f"{commit0}..HEAD")
        return _get_shortstat_total(diff_str)

    def apply_and_diff_commit_pairs(
        self,
    ) -> list[tuple[int, int, git.Commit, git.Commit]]:
        commits = self.get_commit_list()
        print_all_commits(commits)
        print("Iterate...")
        results = []
        for i, commit1 in enumerate(commits):
            (commit0,) = commit1.parents  # will fail if more than one parent
            # print(f"Start at {_format_commit(commit0)}")
            with self.in_tmp_branch(commit1):
                # print(f"Apply {_format_commit(commit1)}")
                diff_count1 = self.count_changed_lines_since(commit0)
                if diff_count1 is None:
                    continue
                for commit2, rel_diff, rel_diff_c in self.apply_and_diff_each_commit2(
                    commit0, commit1, diff_count1, commits[i + 1 :]
                ):
                    print(f"{rel_diff or '':>4} {_format_commits(commit1, commit2)}")
                    if rel_diff is not None and rel_diff_c is not None:
                        results.append((rel_diff_c, rel_diff, commit1, commit2))
        return results

    def apply_and_diff_each_commit2(
        self,
        commit0: git.Commit,
        commit1: git.Commit,
        diff_count1: int,
        commits: Iterable[git.Commit],
    ) -> Generator[tuple[git.Commit, int | None, int | None], None, None]:
        for commit2 in commits:
            self.repo.git.reset("--hard", commit1)
            # print(f"Apply {_format_commit(commit2)}")
            try:
                self.repo.git.cherry_pick(commit2, "--keep-redundant-commits")
            except git.GitCommandError:
                yield commit2, None, None
                continue
            diff_count2 = self.count_changed_lines_since(commit0)
            rel_diff = diff_count2 - diff_count1
            commit_diff_str = self.repo.git.show(commit2, format="", shortstat=True)
            rel_diff_c = rel_diff - _get_shortstat_total(commit_diff_str)
            if rel_diff_c >= 0:
                # this commit has no influence on the prev commit.
                # so skip this whole proposed squash
                yield commit2, None, None
            else:
                yield commit2, rel_diff, rel_diff_c

    @contextlib.contextmanager
    def in_tmp_branch(self, commit: git.Commit) -> Generator[git.Head, None, None]:
        repo = self.repo
        prev_active_branch = repo.active_branch
        tmp_branch = repo.create_head(_TmpBranchName, commit.hexsha, force=True)
        repo.git.checkout(tmp_branch)
        try:
            yield tmp_branch
        except git.GitCommandError as exc:
            print("Git exception occurred. Current git status:")
            print(repo.git.status())
            raise exc
        finally:
            repo.git.reset("--hard")
            repo.git.checkout(prev_active_branch)
            repo.delete_head(_TmpBranchName, force=True)


def _format_commit(commit: git.Commit) -> str:
    return f"{str(commit):8.8} {commit.message.splitlines()[0]}"


def _format_commits(commit1: git.Commit, commit2: git.Commit) -> str:
    return f"{_format_commit(commit1)} -- {_format_commit(commit2)}"


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


def _get_shortstat_total(shortstat_output: str) -> int:
    """Parse total insertions and deletions in ``git --shortstat``

    >>> _get_shortstat_total(" 2 files changed, 1 insertion(+), 5 deletions(-)")
    6
    >>> _get_shortstat_total(" 1 file changed, 3 insertions(+)")
    3
    >>> _get_shortstat_total(" 2 files changed, 1 deletion(-)")
    1

    """
    match = SHORTSTAT_RE.match(shortstat_output)
    if not match:
        raise RuntimeError("Can't parse git --shortstat output {shortstat_output!r}")
    return int(match.group(1) or 0) + int(match.group(2) or 0)


def print_all_commits(commits: Iterable[git.Commit]) -> None:
    print("All commits:")
    for commit in commits:
        print("  ", _format_commit(commit), sep="")


def print_results(results: list[tuple[int, int, git.Commit, git.Commit]]) -> None:
    print("Done. Results:")
    results.sort(key=lambda x: x[0])
    for (c_, c, commit1, commit2) in results:
        print(
            "***",
            c_,
            c,
            "commits:",
            _format_commits(commit1, commit2),
        )


def main() -> None:
    helper = GitHelper(".")
    results = helper.apply_and_diff_commit_pairs()
    print_results(results)


if __name__ == "__main__":
    main()