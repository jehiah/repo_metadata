import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import urllib

from fetcher import fetch_all

endpoint = "https://api.github.com/repos/%s/issues/comments?"

def cache_comments(raw_comments):
    if not os.path.exists(tornado.options.options.comment_cache_dir):
        os.makedirs(tornado.options.options.comment_cache_dir)
    for comment in raw_comments:
        filename = os.path.join(tornado.options.options.comment_cache_dir, "%d.json" % comment['id'])
        if os.path.exists(filename):
            logging.warning('unlinking existing filename %s', filename)
            os.unlink(filename)
        logging.info('creating %s', filename)
        open(filename, 'w').write(json.dumps(comment))

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, 
        per_page=tornado.options.options.per_page, 
        direction=tornado.options.options.direction, 
        since=tornado.options.options.since))
    logging.info('fetching comments for %r', tornado.options.options.repo)
    headers = {"Content-Type":"application/vnd.github-commitcomment.full+json"}
    raw_comments = fetch_all(url, limit=tornado.options.options.limit, headers=headers, callback=cache_comments)
    logging.debug(len(raw_comments))


if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("comment_cache_dir", type=str, default="", help="directory to cache comments")
    tornado.options.define("limit", default=None, type=int, help="max number of records to fetch")
    tornado.options.define("per_page", default=100, type=int)
    tornado.options.define("direction", default="asc")
    tornado.options.define("since", default="")
    tornado.options.parse_command_line()

    if not tornado.options.options.comment_cache_dir:
        comment_cache_dir = os.path.join("../repo_cache/comment_cache", tornado.options.options.repo.replace("/","_"))
        if not os.path.exists(comment_cache_dir):
            os.makedirs(comment_cache_dir)
        tornado.options.options.comment_cache_dir = comment_cache_dir
    
    assert tornado.options.options.repo
    run()
