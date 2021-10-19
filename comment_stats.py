import json
import tornado.options
import glob
import logging
import os.path
from collections import defaultdict
import datetime
from formatters import _github_dt
from helpers import cache_dir

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
    
    col_format = "%4d"
    empty_format = "   ."
    dash_format = "----"
    if group_by == "week":
        col_format = "%6d"
        empty_format = "     ."
        dash_format = "------"
    
    columns = sorted(columns)
    rows = []
    for login in sorted(data.keys(), key=unicode.lower):
        total = sum(data[login].values()) / len(filter(lambda x: True if x is not None else False, data[login].values()))
        rows.append(["%20s" % login] + map(lambda x: col_format % data[login][x] if data[login][x] else empty_format, columns) + [col_format % total])
    rows.append(["%20s" % "-----"] + map(lambda x: dash_format, columns) + [dash_format])
    rows.append(["%20s" % "total"] + map(lambda x: col_format % sum(map(lambda xx: data[xx][x], data.keys())), columns) + [""])
    rows.append(["%20s" % "uniq"] + map(lambda x: col_format % sum(map(lambda xx: 1 if data[xx][x] else 0, data.keys())), columns) + [""])
    return ["%20s " % "login"] + map(lambda x: "%6s" % x[2:], columns) + [" avg"], rows

_cache = {}
def cached_issue_assignee(issue_number):
    if issue_number not in _cache:
        _cache[issue_number] = issue_assignee(issue_number)
    return _cache[issue_number]

def issue_assignee(issue_number):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "issues_cache", o.repo)
    filename = os.path.join(dirname, issue_number + ".json")
    if not os.path.exists(filename):
        return None
    body = json.loads(open(filename, 'r').read())
    user = (body.get('assignee', {}) or {}).get('login')
    if not user:
        user = (body.get('user', {}) or {}).get('login')
    return user


def load_data(min_dt):
    o = tornado.options.options
    for dirname in [cache_dir(o.cache_base, "comment_cache", o.repo), cache_dir(o.cache_base, "review_cache", o.repo)]:
        for filename in glob.glob(os.path.join(dirname, "*.json")):
            comment = json.loads(open(filename, 'r').read())
            dt = _github_dt(comment["created_at"])
            if dt < min_dt:
                logging.debug("skipping %s dt %s < %s", comment["id"], comment["created_at"], min_dt)
                continue
            issue_number = None
            if comment.get('issue_url'):
                issue_number = comment['issue_url'].split('/')[-1]
            elif comment.get("_links",{}).get("pull_request"):
                issue_number = comment["_links"]["pull_request"]["href"].split("/")[-1]
            if not issue_number:
                assert False, comment
            if o.skip_self_comments:
                if cached_issue_assignee(issue_number) == comment['user']['login']:
                    continue
            
            yield dict(
                id=comment['id'],
                created_at=dt,
                login=comment['user']['login'],
                issue_number=issue_number,
            )

def group_by_column(dt):
    if tornado.options.options.group_by == "month":
        return dt.strftime("%Y/%m")
    start = dt - datetime.timedelta(days=dt.weekday())
    return start.strftime("%Y/%m/%d")

if __name__ == "__main__":
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("min_dt", type=str, default=datetime.datetime(2016,1,1).strftime('%Y-%m-%d'), help="YYYY-mm-dd")
    tornado.options.define("group_by", type=str, default="month", help="month|week")
    tornado.options.define("skip_self_comments", type=bool, default=False)
    tornado.options.options.parse_command_line()

    o = tornado.options.options
    assert o.group_by in ["week", "month"]
    assert o.repo
    
    min_dt = datetime.datetime.strptime(o.min_dt, '%Y-%m-%d')
    records = list(load_data(min_dt))

    columns, rows = build_table(records, o.group_by) 
    print "|".join(columns)
    for row in rows:
        print " | ".join(row)
    