import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import urllib

from fetcher import fetch_all
from formatters import _github_dt
from helpers import cache_dir

_ENDPOINT_PATTERN = "https://api.github.com/repos/%s/%s/comments?"
endpoint = ""

def cache_comments(raw_comments):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, cache_type_dir(), o.repo)
    for comment in raw_comments:
        filename = os.path.join(dirname, "%d.json" % comment['id'])
        if os.path.exists(filename):
            logging.warning('unlinking existing filename %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(comment))
    if raw_comments:
        logging.info("dt %s", _github_dt(raw_comments[-1]["created_at"]))

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = _ENDPOINT_PATTERN % (tornado.options.options.repo, tornado.options.options.comment_type)
    url = endpoint + urllib.urlencode(dict(access_token=token, 
        per_page=tornado.options.options.per_page, 
        direction=tornado.options.options.direction, 
        since=tornado.options.options.since))
    logging.info('fetching comments for %r', tornado.options.options.repo)
    headers = {"Content-Type":"application/vnd.github-commitcomment.full+json"}
    raw_comments = fetch_all(url, limit=tornado.options.options.limit, headers=headers, callback=cache_comments)
    logging.debug(len(raw_comments))

def cache_type_dir():
    return "comment_cache" if tornado.options.options.comment_type == "issues" else "review_cache"

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("limit", default=None, type=int, help="max number of records to fetch")
    tornado.options.define("per_page", default=100, type=int)
    tornado.options.define("direction", default="asc")
    tornado.options.define("since", default="")
    tornado.options.define("comment_type", default="issues", help="issues|pulls")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    assert o.comment_type in ['issues', 'pulls']
    assert o.repo and '/' in o.repo
    run()
