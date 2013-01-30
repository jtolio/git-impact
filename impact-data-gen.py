#!/usr/bin/env python

"""
Generate impact data from a git repo

Usage:

  ~/your/git/repo$ /path/to/impact-data-gen.py > /path/to/impact-data.js
"""

import json
import itertools
import subprocess
from collections import defaultdict

BUCKET_SIZE = 60 * 60 * 24 * 7  # size of a bucket in seconds
MAX_BUCKETS = None  # the max number of recent buckets to show


def sanitize_author(name, email):
    """Takes a name and an email and returns a sanitized name for display use
    """
    # deal with inconsistent email addresses/names in commits.
    # feel free to fill this method out.
    return name


def get_commits():
    """Returns an iterable of all the commits in the project's history.

    Will return tuples of the form
        (date, author, insertion_count, deletion_count, file_count)

    where date is seconds from epoch.
    """

    proc = subprocess.Popen(
            ["git", "log", "--full-history",
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
            insertions, deletions, path = pop_line().strip().split()
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


def make_impact_data(commits):
    """From an iterable of commit tuples (see get_commits), returns a
    dictionary of useful aggregate data for use in an impact graph.

    Return value of the form

    {"max_bucket_size": <int>,  # The largest size of any bucket
     "authors": <list>,
     "buckets": <list>}

    "authors" is a list of dictionaries of the form

    {"author_id": <string>,  # the author's short id
     "name": <string>,  # the author's display name
     "message": <string>}  # a summary of the author's contributions

    "buckets" is a list of dictionaries of the form

    {"date": <int>,  # seconds from epoch for the start of this bucket
     "contributions: <list>}

    "contributions" is a list of dictionaries of the form

    {"author_id": <string>,  # the author's id
     "size": <int>}  # the size of the contribution
    """

    authors = {}
    author_starts = {}
    author_ends = {}
    author_ids = {}
    author_id_gen = itertools.count()
    buckets = defaultdict(lambda: [])
    max_size = 0

    # figure out what we need to do to filter out old buckets if MAX_BUCKETS
    # is not None
    commits = sorted(commits)
    if commits and MAX_BUCKETS is not None:
        latest = commits[-1][0]
        latest_bucket = int(latest / BUCKET_SIZE)
        oldest_allowed = (latest_bucket - MAX_BUCKETS + 1) * BUCKET_SIZE
    else:
        oldest_allowed = float('-inf')

    # find all info we can about all the authors and bucketize commits
    for date, author, insertions, deletions, files in commits:
        if author not in author_ids:
            author_id = str(next(author_id_gen))
            author_ids[author] = author_id
            authors[author_id] = {
                    "insertions": 0,
                    "deletions": 0,
                    "files": 0,
                    "commits": 0,
                    "name": author}
        else:
            author_id = author_ids[author]
        bucket_id = int(date / BUCKET_SIZE)
        if author_id not in author_starts:
            author_starts[author_id] = bucket_id
        author_ends[author_id] = bucket_id

        if date < oldest_allowed:
            continue

        author = authors[author_id]
        author["insertions"] += insertions
        author["deletions"] += deletions
        author["files"] += files
        author["commits"] += 1
        size = insertions + deletions
        buckets[bucket_id].append((date, author_id, size))

    # make sure the buckets are sorted in contribution order, make sure
    # to zero-fill contributionless authors that have contributions before and
    # after this bucket
    fixed_buckets = []
    for bucket_id in sorted(buckets.keys()):
        bucket = buckets[bucket_id]
        bucket.sort()
        bucket_date = bucket[0][0]
        contributions = defaultdict(lambda: 0)
        bucket_size = 0
        for _, author_id, size in bucket:
            contributions[author_id] += size
            bucket_size += size
        max_size = max(max_size, bucket_size)
        contributions_sorted = sorted(
                ((size, author_id)
                 for author_id, size in contributions.iteritems()),
                reverse=True)
        for author_id in authors.iterkeys():
            if author_id not in contributions and (
                    author_starts[author_id] <= bucket_id <=
                    author_ends[author_id]):
                contributions_sorted.append((0, author_id))
        fixed_buckets.append({
                "date": bucket[0][0],
                "contributions": [{"author_id": author_id, "size": size}
                                 for size, author_id in contributions_sorted]})

    # sort authors alphabetically, clean up our data about them to conform with
    # what the impact graphing expects
    fixed_authors = []
    for author_id, data in sorted(
            authors.iteritems(), key=lambda item: item[1]["name"].lower()):
        if data["commits"] == 0:
            continue
        fixed_authors.append({
            "author_id": author_id,
            "name": data["name"],
            "message": ("{commits} commits, "
                        "{insertions} additions, "
                        "{deletions} deletions, "
                        "{files} files").format(**data)})

    # return the data
    return {"max_bucket_size": max_size,
            "buckets": fixed_buckets,
            "authors": fixed_authors}


def main():
    # output nice javascript
    print "var chart_data ="
    print json.dumps(make_impact_data(get_commits()), indent=2), ";"


if __name__ == "__main__":
    main()
