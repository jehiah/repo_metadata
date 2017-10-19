import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import glob
import urllib
import datetime

from fetcher import fetch_all, fetch_one

endpoint = "https://api.github.com/repos/%s/issues?"
ISSUE_ENDPOINT = "https://api.github.com/repos/%s/issues/%%d?"
now = datetime.datetime.utcnow()

def cache_issues(raw_issues):
    if not os.path.exists(tornado.options.options.issue_cache_dir):
        os.makedirs(tornado.options.options.issue_cache_dir)
    for issue in raw_issues:
        filename = os.path.join(tornado.options.options.issue_cache_dir, "%d.json" % issue['number'])
        if os.path.exists(filename):
            logging.info('removing existing %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(issue))

def stale_issues(cache_dir):
    stale = set()
    for filename in glob.glob(cache_dir + "/*.json"):
        issue = json.loads(open(filename, 'r').read())
        if issue['state'] == "open":
            stale.add(issue['number'])
    logging.info('found %d possibly stale cached open issues', len(stale))
    return stale

def run():
    global endpoint
    o = tornado.options.options
    endpoint = endpoint % o.repo
    issue_endpoint = (ISSUE_ENDPOINT % o.repo) + urllib.urlencode(dict(access_token=o.access_token))
    if "stale" in o.state:
        for issue_number in stale_issues(o.issue_cache_dir):
            issue = fetch_one(issue_endpoint % issue_number)
            filename = os.path.join(tornado.options.options.issue_cache_dir, "%d.json" % issue_number)
            if os.path.exists(filename):
                logging.info('removing existing %s', filename)
                os.unlink(filename)
            logging.info('updating %s', filename)
            open(filename, 'w').write(json.dumps(issue))
            
            
    for state in o.state:
        if state == "stale":
            continue
        url = endpoint + urllib.urlencode(dict(access_token=o.access_token, per_page=100, filter='all', state=state))
        logging.info('fetching %s issues for %r', state, o.repo)
        raw_issues = fetch_all(url, limit=o.limit, callback=cache_issues)
        logging.info("got %d %s issues", len(raw_issues), state)

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("issue_cache_dir", type=str, default="../repo_cache/issue_cache", help="directory to cache issues")
    tornado.options.define("state", type=str, default=["stale", "open", "closed"], multiple=True)
    tornado.options.define("limit", type=int, default=1000)
    tornado.options.parse_command_line()
    
    assert tornado.options.options.repo
    run()
