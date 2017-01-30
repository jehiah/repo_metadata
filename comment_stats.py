#
# 
# features
# RFR
# LGTM
# no comments before LGTM
# length of text
# length of issue description
# number of your comments on your PR's
# number of your comments on other PR's
# number of comments on your PR's
# median words per comment
# images
# multi-line code blocks in comments
# checklists
# unfinished checklists
# finished checklists
# time to respond to comments (not sure this makes sense as many are unresponded to?)
# delay in feedback comments
# RFR to close duration

# Execution phases
#  - generate numbers for everyone
#  - generate normals
#  - generate a summary for each individual comparing them to average.
#  - give +/- from previous time period
#  - reinforce the value of doing better

import json
import tornado.options
import glob
import logging
import csv
import sys
import os.path
from collections import defaultdict, namedtuple
import datetime
import re

from textstat.textstat import textstat
from formatters import _github_dt

Feature = namedtuple('Feature', ['feature', 'user', 'value'])
        
def process_comment(comment):
    login = comment["user"]["login"]
    body = comment["body"]
    
    yield Feature("comment_count", login, 1) 
    if "RFR" in body and "not RFR" not in body:
        yield Feature('RFR', login, 1)
    if "RFM" in body and "not RFM" not in body:
        yield Feature("RFM", login, 1)
    if "LGTM" in body:
        yield Feature("LGTM", login, 1)
    if r"```" in body:
        yield Feature("code_block", login, 1)
    if r"@" in body:
        yield Feature("mention", login, 1)
    if "![" in body:
        yield Feature("image", login, 1)
    if " [ ]" in body or " [x]" in body:
        yield Feature("checklist", login, 1)
    for field in [":thumbsup:", "+1", ":ship:", ":shipit:", ":rocket:"]:
        if field in body:
            yield Feature(field, login, 1)
    
    txt = _clean_body(body)
    if not txt:
        return
    # yield Feature("avg_sentences_per_comment", login, textstat.sentence_count(txt))
    yield Feature("sentences", login, textstat.sentence_count(txt))

    if 'https://' in txt or 'http://' in txt:
        yield Feature('with_link', login, 1)
    issues = re.findall("#[0-9]{4,5}", txt)
    if issues:
        yield Feature("issue_crosslink", login, len(issues))
    
    if comment.get('issue_url'):
        issue_number = comment['issue_url'].split('/')[-1]
        if cached_issue_assignee(issue_number) == login:
            yield Feature("self_comment", login, 1)

    # print login, txt.encode('utf-8')
    
def _clean_body(t):
    t = re.sub('```.*?```', '', t, flags=re.MULTILINE|re.DOTALL)
    t = re.sub('\!\[.+\]\(.+\)', '', t, flags=re.MULTILINE|re.DOTALL)
    t = re.sub('(RFR|RFM|LGTM|:thumbsup:)', '', t)
    return t
            
def combine_features(feature, values):
    if feature == "avg_sentences_per_comment":
        return sum(values)/len(values)
    return sum(values)

def load_comments():
    for filename in glob.glob("%s/*.json" % tornado.options.options.comment_cache_dir):
        comment = json.loads(open(filename, 'r').read())
        yield comment


class Summary(object):
    def __init__(self):
        self.comments = []
    
    def load_data_for_interval(self, interval):
        assert isinstance(interval, datetime.timedelta)
        min_dt = datetime.datetime.utcnow() - interval
        for filename in glob.glob("%s/*.json" % tornado.options.options.comment_cache_dir):
            comment = json.loads(open(filename, 'r').read())
            if _github_dt(comment["created_at"]) < min_dt:
                logging.info("skipping %s dt %s < %s", comment["id"], comment["created_at"], min_dt)
                continue
            self.comments.append(comment)
    
    def process_features(self):
        d = defaultdict(lambda :defaultdict(list))
        features = set()
        for comment in self.comments:
            for f in process_comment(comment):
                features.add(f.feature)
                d[f.user][f.feature].append(f.value)
        
        return d

def text_summary(d):
    for user, user_data in sorted(d.items()):
        print "*" * 10
        print user.upper()
        
        data = [[combine_features(feature, values), feature] for feature, values in user_data.items()]
        for count, feature in sorted(data, reverse=True):
            print "%3d" % count, feature

def csv_columns(d):
    columns = set(["user"])
    for user_data in d.values():
        columns |= set(user_data.keys())
    return columns

def csv_summary(d, write_headers=True, columns=None, **kwargs):
    if not columns:
        columns = sorted(list(csv_columns(d)))
    o = csv.DictWriter(sys.stdout, columns)
    if write_headers:
        o.writeheader()
    
    for user, user_data in sorted(d.items()):
        row = dict(user=user)
        row.update(kwargs)
        for feature, values in user_data.items():
            row[feature] = "%d" % combine_features(feature, values)
        o.writerow(row)

_cache = {}
def cached_issue_assignee(issue_number):
    if issue_number not in _cache:
        _cache[issue_number] = issue_assignee(issue_number)
    return _cache[issue_number]

def issue_assignee(issue_number):
    filename = os.path.join(tornado.options.options.issue_cache_dir, issue_number + ".json")
    if not os.path.exists(filename):
        return None
    body = json.loads(open(filename, 'r').read())
    user = (body.get('assignee', {}) or {}).get('login')
    if not user:
        user = (body.get('user', {}) or {}).get('login')
    return user

def run():
    s = Summary()
    s.load_data_for_interval(datetime.timedelta(days=tornado.options.options.interval))
    f = s.process_features()
    if tornado.options.options.format == "csv":
        csv_summary(f)
    else:
        text_summary(f)

def run_by_month():
    data = defaultdict(Summary)
    min_dt = None
    if tornado.options.options.min_dt:
        min_dt = datetime.datetime.strptime(tornado.options.options.min_dt, '%Y-%m-%d')
        
    for comment in load_comments():
        dt = _github_dt(comment["created_at"])
        if min_dt and dt < min_dt:
            continue
        data["%d-%d" % (dt.year, dt.month)].comments.append(comment)
    
    features = []
    columns = set()
    for yyyymm, summary in data.items():
        f = summary.process_features()
        columns |= csv_columns(f)
        features.append((yyyymm,f))
    
    columns.remove('user')
    columns = ["user", "yyyymm"] + sorted(list(columns))
    for i, v in enumerate(features):
        yyyymm, f = v
        csv_summary(f, write_headers=(i == 0), columns=columns, yyyymm=yyyymm)

if __name__ == "__main__":
    tornado.options.define("comment_cache_dir", type=str, default="../repo_cache/comment_cache", help="directory to cache comments")
    tornado.options.define("issue_cache_dir", type=str, default="../repo_cache/issue_cache", help="directory to cache issues")
    tornado.options.define("interval", type=int, default=28, help="number of days to genreate stats for")
    tornado.options.define("min_dt", type=str, default=None, help="YYYY-mm-dd")
    tornado.options.define("run_by_month", type=bool, default=False)
    tornado.options.define("format", type=str, default="txt")
    tornado.options.options.parse_command_line()

    if tornado.options.options.run_by_month:
        assert tornado.options.options.format == "csv"
        run_by_month()
    else:
        assert not tornado.options.options.min_dt
        run()