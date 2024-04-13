#!python3.12

import sys
assert sys.version_info >= (3, 9), "incompatible python version"
import json
import tornado.options
import datetime
import logging
import os
import glob
from collections import defaultdict
from operator import itemgetter

from formatters import _github_dt
from helpers import cache_dir
from google_sheets import Sheet

def load_pr(issue_number):
    dirname = cache_dir(o.cache_base, "pulls_cache", o.repo)
    filename = os.path.join(dirname, "%s.json" % issue_number)
    if not os.path.exists(filename):
        return
    with open(filename, 'r') as f:
        return json.load(f)

def load_data(min_dt, max_dt):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "issues_cache", o.repo)
    for issue_file in glob.glob(os.path.join(dirname, '*.json')):
        with open(issue_file, 'r') as f:
            issue = json.load(f)
            dt = _github_dt(issue['created_at'])
            if dt < min_dt:
                continue
            if dt > max_dt:
                continue

            login = issue["user"]["login"]
            for assignee in issue["assignees"]: # pick a random one?
                login = assignee["login"]
            
            if not issue.get("pull_request"):
                logging.debug("skipping ISSUE %s for %s - %s", issue["number"], login, issue["title"])
                continue
            
            if o.login and o.login != login:
                logging.debug("skipping %s for %s - %s", issue["number"], login, o.login)
                continue
            
            if o.skip_unmerged and issue['state'] == 'closed':
                pr_data = load_pr(issue["number"])
                if pr_data and not pr_data["merged_at"]:
                    logging.debug("skipping unmerged closed PR %s for %s - %s", issue["number"], login, issue["title"])
                    continue
            
            yield dict(
                issue_number=issue["number"],
                login=login,
                created_at=dt,
                labels = list(map(itemgetter('name'), issue["labels"])),
                title=issue["title"],
            )

def build_table(records, group_by, f=None, summary=True):
    if callable(f):
        records = list(filter(f, records))
    def inner():
        return defaultdict(int)
    data = defaultdict(inner)
    for row in records:
        data[row['login']][group_by_column(row['created_at'])] += 1
    
    columns = set()
    for datasets in list(data.values()):
        columns |= set(datasets.keys())
    
    col_format = "%3d"
    empty_format = "  ."
    dash_format = "---"
    if group_by == "week":
        col_format = "%6d"
        empty_format = "     ."
        dash_format = "------"
    if not summary:
        empty_format = ""
    
    columns = sorted(columns)
    rows = []
    for login in sorted(list(data.keys()), key=str.lower):
        total = sum(data[login].values()) / len([x for x in list(data[login].values()) if (True if x is not None else False)])
        extra = []
        if summary:
            extra = [col_format % total]
        rows.append(["%20s" % login] + [col_format % data[login][x] if data[login][x] else empty_format for x in columns] + extra)
    if summary:
        rows.append(["%20s" % "-----"] + [dash_format for x in columns] + [dash_format])
        rows.append(["%20s" % "total"] + [col_format % sum([data[xx][x] for xx in list(data.keys())]) for x in columns] + [""])
        rows.append(["%20s" % "uniq"] + [col_format % sum([1 if data[xx][x] else 0 for xx in list(data.keys())]) for x in columns] + [""])
    extra = []
    if summary:
        extra = [" avg"]
    return ["%20s " % "login"] + [x[2:] for x in columns] + extra, rows

def group_by_column(dt):
    if tornado.options.options.group_by == "month":
        return dt.strftime("%Y/%-m")
    start = dt - datetime.timedelta(days=dt.weekday())
    return start.strftime("%Y/%m/%d")


if __name__ == "__main__":
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("min_dt", type=str, default=datetime.datetime(2020,1,1).strftime('%Y-%m-%d'), help="YYYY-mm-dd")
    tornado.options.define("max_dt", type=str, default=datetime.datetime.utcnow().strftime('%Y-%m-%d'), help="YYYY-mm-dd")
    tornado.options.define("group_by", type=str, default="month", help="month|week")
    tornado.options.define("skip_unmerged", type=bool, default=True, help="skip closed but unmerged PR's")
    tornado.options.define("bug_report", type=bool, default=False, help="show summary of 'bug' PR's")
    tornado.options.define("login", type=str, default=None)
    tornado.options.define("spreadsheet_id", type=str, default=None, help="google spreadsheet id to update")
    tornado.options.parse_command_line()
    o = tornado.options.options
    
    assert o.group_by in ["week", "month"]
    assert o.repo

    sheet = None
    if o.spreadsheet_id:
        sheet = Sheet(o.spreadsheet_id)
    
    min_dt = datetime.datetime.strptime(o.min_dt, '%Y-%m-%d')
    max_dt = datetime.datetime.strptime(o.max_dt, '%Y-%m-%d')
    records = list(load_data(min_dt, max_dt))
    for record in records:
        logging.debug("PR %s for %s - %s", record["issue_number"], record["login"], record["title"])
        
    
    print("")
    print("PR's by assignee by month created")
    columns, rows = build_table(records, o.group_by, summary=sheet is None) 
    print("|".join(columns))
    for row in rows:
        print(" | ".join(row))
        if sheet:
            for i, cell in enumerate(row):
                if i > 0 and cell.strip():
                    sheet.update_cell(row[0].strip(), columns[i].strip(), cell.strip())
    
    if sheet:
        sheet.batch_update()

    print()

    if o.bug_report:
        print("")
        print("PR's with \"bug\" label by assignee by month created")
        columns, rows = build_table(records, o.group_by, lambda x: 'bug' in x['labels'], summary=sheet is None)
        print("|".join(columns))
        for row in rows:
            print(" | ".join(row))
    
    