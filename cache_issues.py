import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import urllib
import datetime

from fetcher import fetch_all

endpoint = "https://api.github.com/repos/%s/issues?"
now = datetime.datetime.utcnow()

def cache_issues(raw_issues):
    if not os.path.exists(tornado.options.options.issue_cache_dir):
        os.makedirs(tornado.options.options.issue_cache_dir)
    for issue in raw_issues:
        filename = os.path.join(tornado.options.options.issue_cache_dir, "%d.json" % issue['number'])
        if os.path.exists(filename):
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(issue))

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, filter='all', state='closed'))
    logging.info('fetching closed issues for %r', tornado.options.options.repo)
    raw_issues = fetch_all(url, limit=tornado.options.options.limit, callback=cache_issues)
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, filter='all', state='open'))
    logging.info('fetching open issues for %r', tornado.options.options.repo)
    raw_issues = fetch_all(url, limit=tornado.options.options.limit, callback=cache_issues)
    logging.info("got %d", len(raw_issues))
    

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("issue_cache_dir", type=str, default="../repo_cache/issue_cache", help="directory to cache issues")
    tornado.options.define("limit", type=int, default=1000)
    tornado.options.parse_command_line()
    
    assert tornado.options.options.repo
    run()
