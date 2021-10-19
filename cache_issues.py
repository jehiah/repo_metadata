import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import glob
import urllib
import datetime

from fetcher import fetch_all, fetch_one
from helpers import cache_dir

endpoint = "https://api.github.com/repos/%s/%s?"
ISSUE_ENDPOINT = "https://api.github.com/repos/%s/%s/%%d?"
now = datetime.datetime.utcnow()

updated_issues = set()

def cache_issues(raw_issues):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "%s_cache" % o.issue_type, o.repo)
    for issue in raw_issues:
        filename = os.path.join(dirname, "%d.json" % issue['number'])
        if os.path.exists(filename):
            logging.warning('removing existing %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(issue))
        updated_issues.add(issue['number'])

def cache_issue(issue_number):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "%s_cache" % o.issue_type, o.repo)
    issue_endpoint = (ISSUE_ENDPOINT % (o.repo, o.issue_type))
    issue = fetch_one(issue_endpoint % issue_number)
    filename = os.path.join(dirname, "%d.json" % issue_number)
    if os.path.exists(filename):
        logging.warning('removing existing %s', filename)
        os.unlink(filename)
    logging.info('updating %s', filename)
    open(filename, 'w').write(json.dumps(issue))
    

def stale_issues():
    stale = set()
    dirname = cache_dir(o.cache_base, "%s_cache" % o.issue_type, o.repo)
    for filename in glob.glob(dirname + "/*.json"):
        issue = json.loads(open(filename, 'r').read())
        if issue['state'] == "open":
            if issue['number'] in updated_issues:
                continue
            stale.add(issue['number'])
    logging.info('found %d possibly stale cached open issues', len(stale))
    return stale

def fetch_issues(state, repo, limit):
    url = endpoint + urllib.urlencode(dict(per_page=100, filter='all', state=state))
    logging.info('fetching %s issues for %r', state, repo)
    raw_issues = fetch_all(url, limit=limit, callback=cache_issues)
    logging.info("got %d %s issues", len(raw_issues), state)
    

def run():
    global endpoint
    o = tornado.options.options
    endpoint = endpoint % (o.repo, o.issue_type)

    if "open" in o.state:
        fetch_issues("open", o.repo, o.limit)
    
    if "stale" in o.state:
        for issue_number in stale_issues():
            cache_issue(issue_number)

    if "closed" in o.state:
        fetch_issues("closed", o.repo, o.limit)

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("state", type=str, default=["stale", "open", "closed"], multiple=True)
    tornado.options.define("limit", type=int, default=1000)
    tornado.options.define("issue_type", default="issues", help="issues|pulls")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    assert o.repo and '/' in o.repo
    assert o.issue_type in ['issues', 'pulls']

    run()
