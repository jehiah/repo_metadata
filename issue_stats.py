import json
import tornado.options
import datetime
import os
import glob
from collections import defaultdict
from operator import itemgetter
from formatters import _github_dt



def load_data(min_dt):
    for issue_file in glob.glob(os.path.join(tornado.options.options.issue_cache_dir, '*.json')):
        with open(issue_file, 'r') as f:
            issue = json.load(f)
            dt = _github_dt(issue['created_at'])
            if dt < min_dt:
                continue
            login = issue["user"]["login"]
            for assignee in issue["assignees"]: # pick a random one?
                login = assignee["login"]
            yield dict(
                issue_number=issue["number"],
                login=login,
                created_at=dt,
                labels = map(itemgetter('name'), issue["labels"]),
            )

def build_table(records, f=None):
    if callable(f):
        records = filter(f, records)
    def inner():
        return defaultdict(int)
    data = defaultdict(inner)
    for row in records:
        data[row['login']][row['created_at'].strftime("%Y/%m")] += 1
    
    columns = set()
    for datasets in data.values():
        columns |= set(datasets.keys())
    
    columns = sorted(columns)
    rows = []
    for login in sorted(data.keys()):
        total = sum(data[login].values()) / len(columns)
        rows.append(["%14s" % login] + map(lambda x: "%3d" % data[login][x], columns) + ["%3d" % total])
    rows.append(["%14s" % "total"] + map(lambda x: "%3d" % sum(map(lambda xx: data[xx][x], data.keys())), columns) + [""])
    return ["%14s " % "login"] + map(lambda x: x[2:], columns) + [" avg"], rows




if __name__ == "__main__":
    # tornado.options.define("comment_cache_dir", type=str, default="../repo_cache/comment_cache", help="directory to cache comments")
    tornado.options.define("issue_cache_dir", type=str, default="../repo_cache/issue_cache", help="directory to cache issues")
    tornado.options.define("min_dt", type=str, default=datetime.datetime(2016,1,1).strftime('%Y-%m-%d'), help="YYYY-mm-dd")
    
    tornado.options.parse_command_line()
    
    min_dt = datetime.datetime.strptime(tornado.options.options.min_dt, '%Y-%m-%d')
    records = list(load_data(min_dt))
    
    print ""
    print "PR's by assignee by month created"
    columns, rows = build_table(records) 
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)

    print ""
    print "PR's with \"bug\" label by assignee by month created"
    columns, rows = build_table(records, lambda x: 'bug' in x['labels'])
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)
    
    