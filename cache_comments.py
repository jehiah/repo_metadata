import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import urllib
import datetime

from formatters import _github_dt
from helpers import get_link


endpoint = "https://api.github.com/repos/%s/issues/comments?"
now = datetime.datetime.utcnow()

# return start, end, [labels]
def get_issue_data(issue):
    created_at = _github_dt(issue["created_at"])
    if issue['state'] == 'closed':
        closed_at = _github_dt(issue["closed_at"])
    else:
        closed_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    return dict(created_at=created_at, closed_at=closed_at, labels=issue['labels'])
    

def fetch_all(url, limit=None):
    o = []
    http = tornado.httpclient.HTTPClient()
    for x in range(80):
        headers = {"Content-Type":"application/vnd.github-commitcomment.full+json"}
        try:
            resp = http.fetch(url, user_agent='issue fetcher (tornado/httpclient)', headers=headers)
        except tornado.httpclient.HTTPError, e:
            logging.error('failed %r %r', e.response.body, e.response)
            raise e
        data = json.loads(resp.body)
        logging.info('got %d records', len(data))
        logging.debug('%r', data)
        next_url = get_link(resp, 'next')
        o.extend(data)
        cache_comments(data)
        if limit and len(o) > limit:
            logging.info('%d is passed limit of %d', len(o), limit)
            break
        if next_url:
            url = next_url
        else:
            break
    return o

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
    raw_comments = fetch_all(url, limit=tornado.options.options.limit)
    logging.debug(len(raw_comments))
    # issue_data = [get_issue_data(x) for x in raw_issues]
    # run_issues(issue_data)


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
