#!/usr/bin/env python

"""
Generate impact data from a git repo

Usage:

  ./commit-data.py ~/your/git/repo/.git | ./preprocess.py > impact-data.js
"""

import sys
import json
import time
import itertools
import subprocess
from collections import defaultdict


def oldestAllowedContribution(max_buckets):
    return makeBucketId(time.time()) - (max_buckets * 60 * 60 * 24 * 7)


def makeBucketId(timestamp):
    tm = time.gmtime(timestamp)
    week_day = (tm.tm_wday + 1) % 7
    timestamp -= week_day * 24 * 60 * 60
    timestamp = int(timestamp)
    timestamp -= tm.tm_hour * 60 * 60
    timestamp -= tm.tm_min * 60
    timestamp -= tm.tm_sec
    return timestamp + 7 * 60 * 60 + 1


def sanitize(instream):
    """Takes an input stream of newline-delimited lines of the form
    <date> <size> <author> <name> ...

    and returns an iterable of tuples of the form (date, size, author_name)
    """
    for line in instream:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        yield int(parts[0]), int(parts[1]), " ".join(parts[2:])


def make_impact_data(contributions, max_buckets=None):
    """From an iterable of contribution tuples (date, size, author), returns a
    dictionary of useful aggregate data for use in an impact graph.

    Return value of the form

    {"authors": <list>,
     "buckets": <list>}

    "authors" is a list of dictionaries of the form

    {"author_id": <int>,  # the author's short id
     "name": <string>,  # the author's display name
     "total": <int>}  # the author's total

    "buckets" is a list of dictionaries of the form

    {"date": <int>,  # seconds from epoch for the start of this bucket
     "contributions: <list>}

    "contributions" is a list of dictionaries of the form

    {"author_id": <int>,  # the author's id
     "size": <int>}  # the size of the contribution
    """

    authors = {}
    author_starts = {}
    author_ends = {}
    author_ids = {}
    author_id_gen = itertools.count()
    buckets = defaultdict(lambda: [])

    # figure out what we need to do to filter out old buckets if max_buckets
    # is not None
    contributions = sorted(contributions)
    if contributions and max_buckets is not None:
        oldest_allowed = oldestAllowedContribution(max_buckets)
    else:
        oldest_allowed = float('-inf')

    # find all info we can about all the authors and bucketize contributions
    for date, size, author in contributions:
        if author not in author_ids:
            author_id = next(author_id_gen)
            author_ids[author] = author_id
            authors[author_id] = {
                    "total": 0,
                    "name": author}
        else:
            author_id = author_ids[author]
        bucket_id = makeBucketId(date)
        if author_id not in author_starts:
            author_starts[author_id] = bucket_id
        author_ends[author_id] = bucket_id

        if date < oldest_allowed:
            continue

        author = authors[author_id]
        author["total"] += size
        buckets[bucket_id].append((date, author_id, size))

    # make sure the buckets are sorted in contribution order, make sure
    # to zero-fill contributionless authors that have contributions before and
    # after this bucket
    fixed_buckets = []
    for bucket_id in sorted(buckets.keys()):
        bucket = buckets[bucket_id]
        bucket.sort()
        bucket_date = bucket_id
        contributions = defaultdict(lambda: 0)
        bucket_size = 0
        for _, author_id, size in bucket:
            contributions[author_id] += size
            bucket_size += size
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
                "date": bucket_date,
                "contributions":
                    [{"author_id": author_id, "size": size}
                     for size, author_id in contributions_sorted]})

    # sort authors alphabetically, clean up our data about them to conform with
    # what the impact graphing expects
    fixed_authors = []
    for author_id, data in sorted(
            authors.iteritems(), key=lambda item: item[1]["name"].lower()):
        if data["total"] == 0:
            continue
        fixed_authors.append({
            "author_id": author_id,
            "name": data["name"],
            "total": data["total"]})

    # return the data
    return {"buckets": fixed_buckets,
            "authors": fixed_authors}


def main():
    max_buckets = None
    js_var_name = "chart_data"

    if len(sys.argv) > 1:
        js_var_name = sys.argv[1]
    if len(sys.argv) > 2:
        max_buckets = int(sys.argv[2])

    print "var %s = " % js_var_name, json.dumps(
        make_impact_data(
            sanitize(sys.stdin),
            max_buckets=max_buckets),
        indent=2), ";"


if __name__ == "__main__":
    main()
