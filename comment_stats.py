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

import simplejson as json
import tornado.options
import glob
import logging
from collections import defaultdict, namedtuple
import datetime
from textstat.textstat import textstat
import re

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
        

class Summary(object):
    def __init__(self):
        self.comments = []
        min_dt = datetime.datetime.utcnow() - datetime.timedelta(days=tornado.options.options.interval)
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
        
        for user, user_data in sorted(d.items()):
            print "*" * 10
            print user.upper()
            
            data = [[combine_features(feature, values), feature] for feature, values in user_data.items()]
            for count, feature in sorted(data, reverse=True):
                print "%3d" % count, feature


def run():
    s = Summary()
    s.process_features()


if __name__ == "__main__":
    tornado.options.define("comment_cache_dir", type=str, default="comment_cache", help="directory to cache comments")
    tornado.options.define("issue_cache_dir", type=str, default="issue_cache", help="directory to cache issues")
    tornado.options.define("interval", type=int, default=28, help="number of days to genreate stats for")
    tornado.options.options.parse_command_line()

    run()