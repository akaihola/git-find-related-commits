"""Format and output information for the user."""

from typing import Iterable

from git.objects import Commit


def print_all_commits(commits: Iterable[Commit]) -> None:
    """Print out all commits in the given list of commits.

    :param commits: The commits to print

    """
    print("All commits:")
    for commit in commits:
        print("  ", _format_commit(commit), sep="")


def print_results(results: list[tuple[int, int, Commit, Commit]]) -> None:
    """Print the results from comparing all pairs of commits.

    :param results: The commit pairs and their degrees of relatedness

    """
    print("Done. Results:")
    results.sort(key=lambda x: x[0])
    for (c_, c, commit1, commit2) in results:
        print(
            "***",
            c_,
            c,
            "commits:",
            format_commits(commit1, commit2),
        )


def _format_commit(commit: Commit) -> str:
    r"""Format a commit for showing it to the user.

    >>> import git
    >>> commit = git.Commit(
    ...     repo=None,
    ...     binsha=b"foobarbazquux1234567",
    ...     message="line 1\nline 2"
    ... )
    >>> _format_commit(commit)
    '666f6f62 line 1'

    :param commit: The commit to format
    :return: The string containing the formatted commit

    """
    message = (
        commit.message.decode("ascii")
        if isinstance(commit.message, bytes)
        else commit.message
    )
    return f"{str(commit):8.8} {message.splitlines()[0]}"


def format_commits(commit1: Commit, commit2: Commit) -> str:
    r"""Format two commits with a double dash in between.

    >>> import git
    >>> commit1 = git.Commit(
    ...     repo=None,
    ...     binsha=b"foobarbazquux1234567",
    ...     message="commit 1\nline 2"
    ... )
    >>> commit2 = git.Commit(
    ...     repo=None,
    ...     binsha=b"thequickbrownfoxjump",
    ...     message="commit 2\nline 2"
    ... )
    >>> format_commits(commit1, commit2)
    '666f6f62 commit 1 -- 74686571 commit 2'

    :param commit1: The first commit to format
    :param commit2: The second commit to format
    :return: The string containing the formatted commits

    """
    return f"{_format_commit(commit1)} -- {_format_commit(commit2)}"
