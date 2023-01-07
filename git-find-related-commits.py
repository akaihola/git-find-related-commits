#!/usr/bin/env python3

"""Find closely related commits in a Git branch

Adopted from https://github.com/albertz/helpers/blob/master/git-find-related-commits.py

https://stackoverflow.com/questions/66731069/how-to-find-pairs-groups-of-most-related-commits
https://www.reddit.com/r/learnprogramming/comments/pftenx/how_to_cleanup_a_branch_pr_with_huge_number_of/
"""

from __future__ import annotations

import contextlib
import sys
from typing import List, Optional, Tuple

import git  # pip install GitPython

_TmpBranchName = "tmp-find-related-commits"


class GitHelper:
    def __init__(self, repo_dir: str):
        self.repo = git.Repo(repo_dir)
        self.main_branch = "origin/master"
        self.local_branch = self.repo.active_branch
        assert self.local_branch.name != _TmpBranchName

    def get_commit_list(self) -> List[git.Commit]:
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

    def score_commit_pair_squash(
        self, commit1: git.Commit, commit2: git.Commit
    ) -> Tuple[Optional[int], Optional[int], List[str]]:
        (commit0,) = commit1.parents
        # print(f"Start at {_format_commit(commit0)}")
        diffs = []
        rel_diff_c = None
        with self.in_tmp_branch(commit0):
            # print(f"Apply {_format_commit(commit)}")
            try:
                self.repo.git.cherry_pick(commit1, "--keep-redundant-commits")
            except git.GitCommandError:
                return None, None, diffs
            diff_str = self.repo.git.diff(f"{commit0}..HEAD")
            diff_count1 = _count_changed_lines(diff_str)
            diffs.append(diff_str)

            # print(f"Apply {_format_commit(commit)}")
            try:
                self.repo.git.cherry_pick(commit2, "--keep-redundant-commits")
            except git.GitCommandError:
                return None, None, diffs
            diff_str = self.repo.git.diff(f"{commit0}..HEAD")
            diff_count2 = _count_changed_lines(diff_str)
            commit_diff_str = self.repo.git.show(commit2)
            cc = _count_changed_lines(commit_diff_str)
            rel_diff = diff_count2 - diff_count1
            rel_diff_c = rel_diff - cc
            if (
                rel_diff_c >= 0
            ):  # this commit has no influence on the prev commit. so skip this whole proposed squash
                return None, None, diffs
            diffs.append(diff_str)
        rel_diff = diff_count2 - diff_count1
        return rel_diff, rel_diff_c, diffs

    def test(self):
        commits = self.get_commit_list()
        print("All commits:")
        for commit in commits:
            print(f"  {_format_commit(commit)}")
        print("Iterate...")
        results = []
        for i, commit1 in enumerate(commits):
            for commit2 in commits[i + 1 :]:
                c, c_, diffs = self.score_commit_pair_squash(commit1, commit2)
                print(
                    f"{c or '':>4}"
                    f" {_format_commit(commit1)} --"
                    f" {_format_commit(commit2)}"
                )
                if c is not None:
                    results.append((c_, c, [commit1, commit2], diffs))

        print("Done. Results:")
        results.sort(key=lambda x: x[0])
        for c_, c, (commit1, commit2), diffs in results:
            print(
                "***",
                c_,
                c,
                "commits:",
                [_format_commit(commit1), _format_commit(commit2)],
            )

    @contextlib.contextmanager
    def in_tmp_branch(self, commit: git.Commit) -> git.Head:
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


def _format_commit(commit: git.Commit) -> str:
    return f"{str(commit):8.8} {commit.message.splitlines()[0]}"


def _count_changed_lines(s: str) -> int:
    c = 0
    for line in s.splitlines():
        if line.startswith("+ ") or line.startswith("- "):
            c += 1
    return c


def main():
    helper = GitHelper(".")
    helper.test()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
        sys.exit(1)
