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
from collections import namedtuple
import datetime
import re
# from google.cloud import language


from textstat.textstat import textstat
from formatters import _github_dt
from helpers import cache_dir

Feature = namedtuple('Feature', ['feature', 'user', 'value'])
# language_client = language.Client()

        
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
    if "PTAL" in body:
        yield Feature("PTAL", login, 1)
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

    issues = re.findall("\b(CS|BITLY|DATA|DEVOPS)-[0-9]{3,4}\b", txt)
    if issues:
        yield Feature("jira_crosslink", login, len(issues))
    
    if comment.get('issue_url'):
        issue_number = comment['issue_url'].split('/')[-1]
        if cached_issue_assignee(issue_number) == login:
            yield Feature("self_comment", login, 1)
    
    # document = language_client.document_from_text(txt)
    # sentiment = document.analyze_sentiment()
    # logging.info('sentiment score:%r magnitude:%r text %r', sentiment.score, sentiment.magnitude, txt)
    # yield Feature(_sentiment_category(sentiment), login, 1)


def _sentiment_category(sentiment):
    if sentiment.score >= .5:
        return 'comment_positive'
    elif sentiment.score >= .3:
        return 'comment_milidly_positive'
    elif sentiment.score <= -0.5:
        return 'comment_negative'
    elif sentiment.score <= -0.3:
        return 'comment_milidly_negative'
    elif sentiment.magnitude >1:
        return 'comment_mixed'
    else:
        return 'comment_neutral'
    

    # print login, txt.encode('utf-8')
    
def _clean_body(t):
    t = re.sub('```.*?```', '', t, flags=re.MULTILINE|re.DOTALL)
    t = re.sub('\!\[.+\]\(.+\)', '', t, flags=re.MULTILINE|re.DOTALL)
    t = re.sub('(RFR|RFM|LGTM|PTAL|:thumbsup:)', '', t)
    return t.strip()
            
def combine_features(feature, values):
    if feature == "avg_sentences_per_comment":
        return sum(values)/len(values)
    return sum(values)

def load_comments():
    o = tornado.options.options
    for dirname in [cache_dir(o.cache_base, "comment_cache", o.repo), cache_dir(o.cache_base, "review_cache", o.repo)]:
        for filename in glob.glob(os.path.join(dirname, "*.json")):
            comment = json.loads(open(filename, 'r').read())
            yield comment


def comments_for_interval(interval):
    assert isinstance(interval, datetime.timedelta)
    min_dt = datetime.datetime.utcnow() - interval
    for dirname in [cache_dir(o.cache_base, "comment_cache", o.repo), cache_dir(o.cache_base, "review_cache", o.repo)]:
        for filename in glob.glob(os.path.join(dirname, "*.json")):
            comment = json.loads(open(filename, 'r').read())
            if _github_dt(comment["created_at"]) < min_dt:
                logging.debug("skipping %s dt %s < %s", comment["id"], comment["created_at"], min_dt)
                continue
            logging.debug('comment %r', comment)
            yield comment

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

def run_interval():
    for comment in comments_for_interval(datetime.timedelta(days=tornado.options.options.interval)):
        dt = _github_dt(comment["created_at"])
        yyyymm = "%d-%02d" % (dt.year, dt.month)
        for feature in process_comment(comment):
            yield [yyyymm, feature.feature, feature.user, feature.value]

def run_by_month():
    min_dt = None
    if tornado.options.options.min_dt:
        min_dt = datetime.datetime.strptime(tornado.options.options.min_dt, '%Y-%m-%d')
        
    for comment in load_comments():
        dt = _github_dt(comment["created_at"])
        if min_dt and dt < min_dt:
            logging.debug('skipping comment dt %s - %s', dt, min_dt)
            continue
        yyyymm = "%d-%02d" % (dt.year, dt.month)
        for feature in process_comment(comment):
            yield [yyyymm, feature.feature, feature.user, feature.value]

if __name__ == "__main__":
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("interval", type=int, default=28, help="number of days to genreate stats for")
    tornado.options.define("min_dt", type=str, default=None, help="YYYY-mm-dd")
    tornado.options.define("run_by_month", type=bool, default=False)
    tornado.options.options.parse_command_line()

    o = tornado.options.options
    assert o.repo
    out = csv.writer(sys.stdout)
    if o.run_by_month:
        for row in run_by_month():
            out.writerow(row)
    else:
        assert not o.min_dt
        for row in run_interval():
            out.writerow(row)
    