import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import urllib
import os
import os.path

from fetcher import fetch_all

endpoint = "https://api.github.com/repos/%s/issues/events?"


def cache_events(raw_events):
    if not os.path.exists(tornado.options.options.event_cache_dir):
        os.makedirs(tornado.options.options.event_cache_dir)
    for event in raw_events:
        filename = os.path.join(tornado.options.options.event_cache_dir, "%d.json" % event['id'])
        if os.path.exists(filename):
            logging.warning('unlinking existing filename %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(event))

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100))
    logging.info('fetching comments for %r', tornado.options.options.repo)
    fetch_all(url, limit=tornado.options.options.limit, callback=cache_events)

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("event_cache_dir", type=str, help="directory to cache events")
    tornado.options.define("limit", default=2000, type=int, help="max number of records to fetch")
    tornado.options.parse_command_line()
    
    if not tornado.options.options.event_cache_dir:
        event_cache_dir = os.path.join("../repo_cache/event_cache", tornado.options.options.repo.replace("/","_"))
        tornado.options.options.event_cache_dir = event_cache_dir
    
    assert tornado.options.options.repo
    run()
