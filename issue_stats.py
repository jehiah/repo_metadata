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

def build_table(records, group_by, f=None):
    if callable(f):
        records = filter(f, records)
    def inner():
        return defaultdict(int)
    data = defaultdict(inner)
    for row in records:
        data[row['login']][group_by_column(row['created_at'])] += 1
    
    columns = set()
    for datasets in data.values():
        columns |= set(datasets.keys())
    
    col_format = "%3d"
    if group_by == "week":
        col_format = "%6d"
    
    columns = sorted(columns)
    rows = []
    for login in sorted(data.keys()):
        total = sum(data[login].values()) / len(columns)
        rows.append(["%14s" % login] + map(lambda x: col_format % data[login][x], columns) + [col_format % total])
    rows.append(["%14s" % "total"] + map(lambda x: col_format % sum(map(lambda xx: data[xx][x], data.keys())), columns) + [""])
    return ["%14s " % "login"] + map(lambda x: x[2:], columns) + [" avg"], rows

def group_by_column(dt):
    if tornado.options.options.group_by == "month":
        return dt.strftime("%Y/%m")
    start = dt - datetime.timedelta(days=dt.weekday())
    return start.strftime("%Y/%m/%d")


if __name__ == "__main__":
    # tornado.options.define("comment_cache_dir", type=str, default="../repo_cache/comment_cache", help="directory to cache comments")
    tornado.options.define("issue_cache_dir", type=str, default="../repo_cache/issue_cache", help="directory to cache issues")
    tornado.options.define("min_dt", type=str, default=datetime.datetime(2016,1,1).strftime('%Y-%m-%d'), help="YYYY-mm-dd")
    tornado.options.define("group_by", type=str, default="month", help="month|week")
    tornado.options.parse_command_line()
    o = tornado.options.options
    
    assert o.group_by in ["week", "month"]
    
    min_dt = datetime.datetime.strptime(o.min_dt, '%Y-%m-%d')
    records = list(load_data(min_dt))
    
    print ""
    print "PR's by assignee by month created"
    columns, rows = build_table(records, o.group_by) 
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)

    print ""
    print "PR's with \"bug\" label by assignee by month created"
    columns, rows = build_table(records, o.group_by, lambda x: 'bug' in x['labels'])
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)
    
    