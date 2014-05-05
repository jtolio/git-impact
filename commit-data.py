#!/usr/bin/env python

"""
Generate impact data from a git repo

Usage:

  ./commit-data.py ~/your/git/repo/.git | ./preprocess.py > impact-data.js
"""
import sys
import json
import itertools
import subprocess
from collections import defaultdict


def sanitize_author(name, email):
    """Takes a name and an email and returns a sanitized name for display use
    """
    # deal with inconsistent email addresses/names in commits.
    # feel free to fill this method out.
    return name


def get_commits(git_path):
    """Returns an iterable of all the commits in the project's history.

    Will return tuples of the form
        (date, author, insertion_count, deletion_count, file_count)

    where date is seconds from epoch.
    """

    proc = subprocess.Popen(
            ["git", "--git-dir=%s" % git_path, "log", "--full-history",
             "--format=NEW COMMIT%n%ct%n%aN%n%aE", "--numstat"],
            stdout=subprocess.PIPE)
    line_stack = []

    def peek_line():
        if not line_stack:
            line_stack.append(proc.stdout.readline())
        return line_stack[-1]

    def pop_line():
        if line_stack:
            return line_stack.pop()
        return proc.stdout.readline()

    def push_line(line):
        line_stack.append(line)

    def read_commit():
        while peek_line() and not peek_line().strip():
            pop_line()
        if not peek_line(): return None
        assert peek_line().strip() == "NEW COMMIT"
        pop_line()

        date = int(pop_line())
        name = pop_line().strip()
        email = pop_line().strip()
        author = sanitize_author(name, email)

        if peek_line().strip() == "NEW COMMIT":
            return date, author, 0, 0, 0

        pop_line()
        insertion_count = 0
        deletion_count = 0
        file_count = 0
        while peek_line().strip() and peek_line().strip() != "NEW COMMIT":
            insertions, deletions, path = pop_line().strip().split(None, 2)
            if insertions == "-": insertions = 0
            if deletions == "-": deletions = 0
            insertion_count += int(insertions)
            deletion_count += int(deletions)
            file_count += 1

        return date, author, insertion_count, deletion_count, file_count

    while True:
        commit = read_commit()
        if commit is None:
            break
        yield commit


def main():
    if len(sys.argv) > 1:
        git_path = sys.argv[1]
    else:
        git_path = "."
    for date, author, insertions, deletions, _ in get_commits(git_path):
        print date, insertions + deletions, author


if __name__ == "__main__":
    main()
