#!/usr/bin/env python3

"""Find closely related commits in a Git branch.

Copyright (c) 2023 Albert Zeyer, Antti Kaihola
Licensed under the MIT license. For details, see the file ``LICENSE`` in the root of the
repository at https://github.com/akaihola/git-find-related-commits

Adapted from https://github.com/albertz/helpers/blob/master/git-find-related-commits.py

https://stackoverflow.com/questions/66731069/find-pairs-of-most-related-commits
https://www.reddit.com/r/learnprogramming/comments/pftenx/cleanup_pr_lots_of_commits/

"""

from __future__ import annotations

from typing import Generator, Iterable

import git  # pip install GitPython
from git.objects import Commit

from git_find_related_commits.git_helpers import (
    _get_shortstat_total,
    count_changed_lines_since,
    get_commit_list,
    get_main_branch,
    in_tmp_branch,
)
from git_find_related_commits.output import (
    format_commits,
    print_all_commits,
    print_results,
)

TEMPORARY_BRANCH_NAME = "tmp-find-related-commits"


def apply_and_diff_commit_pairs(
    repo: git.Repo, main_branch: str, local_branch: git.Head
) -> list[tuple[int, int, Commit, Commit]]:
    """Compare changed lines of each commit pair.

    :param repo: The Git repository to use
    :param main_branch: The remote main branch, e.g. ``"origin/main"``
    :param local_branch: The local branch whose commits to look at
    :return: List of related commit pairs with scores

    """
    assert local_branch.name != TEMPORARY_BRANCH_NAME

    commits = get_commit_list(repo, main_branch, local_branch)
    print_all_commits(commits)
    print("Iterate...")
    results = []
    for i, commit1 in enumerate(commits):
        (commit0,) = commit1.parents  # will fail if more than one parent
        # print(f"Start at {_format_commit(commit0)}")
        with in_tmp_branch(repo, TEMPORARY_BRANCH_NAME, commit1):
            # print(f"Apply {_format_commit(commit1)}")
            diff_count1 = count_changed_lines_since(repo, commit0)
            if diff_count1 is None:
                continue
            for commit2, rel_diff, rel_diff_c in apply_and_diff_each_commit2(
                repo, commit0, commit1, diff_count1, commits[i + 1 :]
            ):
                print(f"{rel_diff or '':>4} {format_commits(commit1, commit2)}")
                if rel_diff is not None and rel_diff_c is not None:
                    results.append((rel_diff_c, rel_diff, commit1, commit2))
    return results


def apply_and_diff_each_commit2(
    repo: git.Repo,
    commit0: Commit,
    commit1: Commit,
    diff_count1: int,
    commits: Iterable[Commit],
) -> Generator[tuple[Commit, int | None, int | None], None, None]:
    """Compare each newer commit to a given older commit, yield degree of relatedness.

    The repository ``HEAD`` is assumed to point to the older commit.

    :param repo: The Git repository to use
    :param commit0: The parent of the old commit
    :param commit1: The old commit to compare to
    :param diff_count1: Number of changed lines between ``commit0`` and ``commit1``
    :param commits: The new commits to compare
    :yield: Tuples with the new commit and the degree of relatednsess

    """
    for commit2 in commits:
        repo.git.reset("--hard", commit1)
        # print(f"Apply {_format_commit(commit2)}")
        try:
            repo.git.cherry_pick(commit2, "--keep-redundant-commits")
        except git.GitCommandError:
            yield commit2, None, None
            continue
        diff_count2 = count_changed_lines_since(repo, commit0)
        rel_diff = diff_count2 - diff_count1
        commit_diff_str = repo.git.show(commit2, format="", shortstat=True)
        rel_diff_c = rel_diff - _get_shortstat_total(commit_diff_str)
        if rel_diff_c >= 0:
            # this commit has no influence on the prev commit.
            # so skip this whole proposed squash
            yield commit2, None, None
        else:
            yield commit2, rel_diff, rel_diff_c


def main() -> None:
    """Compare pairs of commits in the repository at the current working directory."""
    repo = git.Repo(".")
    main_branch = get_main_branch(repo)
    results = apply_and_diff_commit_pairs(repo, main_branch, repo.active_branch)
    print_results(results)


if __name__ == "__main__":
    main()
