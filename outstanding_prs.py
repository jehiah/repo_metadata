import json
import tornado.options
import datetime
import os
import glob
import logging
from collections import defaultdict
from operator import itemgetter

from formatters import _github_dt
from helpers import cache_dir



def load_data():
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "issues_cache", o.repo)
    for issue_file in glob.glob(os.path.join(dirname, '*.json')):
        with open(issue_file, 'r') as f:
            issue = json.load(f)
            if issue['state'] != 'open':
                continue
            if not issue.get("pull_request"):
                continue
            assignees = map(itemgetter('login'), issue['assignees'])
            if not assignees:
                assignees = [issue["user"]["login"]]
            yield dict(
                issue_number=issue["number"],
                title=issue['title'],
                assignees=assignees,
                updated_at=_github_dt(issue['updated_at']),
                created_at=_github_dt(issue['created_at']),
            )

def build_table(records, f=None):
    if callable(f):
        records = filter(f, records)
    def inner():
        return [0,0,0]
    data = defaultdict(inner)
    
    offset_1w = datetime.datetime.utcnow().replace(hour=0,minute=0) - datetime.timedelta(days=7)
    offset_1m = datetime.datetime.utcnow().replace(hour=0,minute=0) - datetime.timedelta(days=28)
    
    def offset(record):
        if record['created_at'] > offset_1w:
            return 0
        if record['created_at'] > offset_1m:
            return 1
        return 2

    for row in records:
        for login in row['assignees']:
            logging.debug('#%-5d - %-15s - %s', row['issue_number'], login, row['title'])
            data[login][offset(row)] += 1
    
    rows = []
    total = [0,0,0,0]
    for login in sorted(data.keys()):
        row_total = sum(data[login])
        data[login].append(row_total)
        for i, x in enumerate(data[login]):
            total[i] += x
        rows.append(["%14s" % login] + map(lambda x: "%3d" % x, data[login]))
    rows.append(["%14s" % "TOTAL"] + map(lambda x: "%3d" % x, total))
    return ["%14s " % "login", " <7d ", " <28d", ">=28d", "total"], rows




if __name__ == "__main__":
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    assert o.repo
    records = list(load_data())
    
    print ""
    print "PR's by date created by assignee"
    columns, rows = build_table(records) 
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)
    
    