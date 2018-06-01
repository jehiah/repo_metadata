import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import urllib
import os
import functools
import os.path

from fetcher import fetch_all
from helpers import cache_dir

ISSUES_ENDPOINT = "https://api.github.com/repos/%s/issues/events?"

def cache_events(raw_events, repo):
    o = tornado.options.options
    dirname = cache_dir(o.cache_base, "event_cache", repo)
    for event in raw_events:
        filename = os.path.join(dirname, "%d.json" % event['id'])
        if os.path.exists(filename):
            logging.warning('unlinking existing filename %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(event))

def run(repo):
    token = tornado.options.options.access_token
    endpoint = ISSUES_ENDPOINT % repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100))
    logging.info('fetching events for %r', repo)
    fetch_all(url, limit=tornado.options.options.limit, callback=functools.partial(cache_events, repo=repo))

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query", multiple=True)
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.define("limit", default=2000, type=int, help="max number of records to fetch")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    assert o.repo
    for repo in o.repo:
        assert repo
        run(repo)
