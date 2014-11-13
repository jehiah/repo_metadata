import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import glob
import urllib
from collections import defaultdict
import datetime

from formatters import _github_dt


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
    
def get_link(req, key="next"):
    links = req.headers.get('Link')
    if not links:
        return
    for link in links.split(', '):
        url, rel = link.split('; ')
        url = url.strip('<>')
        assert rel.startswith("rel=")
        rel = rel[4:].strip('"')
        if rel == key:
            return url

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
        logging.debug('got %d records', len(data))
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

def get_days_range(dt, count):
    for x in range(count):
        d = dt + datetime.timedelta(days=x)
        if d < now:
            yield d.strftime('%Y-%m-%d')

def get_issue_days(issue):
    delta = issue['closed_at'] - issue['created_at']
    for dt_str in get_days_range(issue['created_at'], delta.days):
        yield dt_str

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
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, direction="desc", sort="created"))
    logging.info('fetching comments for %r', tornado.options.options.repo)
    raw_comments = fetch_all(url, limit=tornado.options.options.limit)
    logging.debug(len(raw_comments))
    # issue_data = [get_issue_data(x) for x in raw_issues]
    # run_issues(issue_data)

def cached_issues():
    for filename in glob.glob(tornado.options.options.issue_cache_dir + '/*.json'):
        f = open(filename, 'r')
        data = json.loads(f.read())
        f.close()
        yield get_issue_data(data)

def run_issues(issue_data):
    
    def newrow():
        return defaultdict(int)
    now = datetime.datetime.utcnow()
    dates = defaultdict(newrow)
    for issue in issue_data:
        for date in get_issue_days(issue):
            dates[date]['all'] += 1
            for label in issue['labels']:
                dates[date][label['name']] += 1
        
        if issue['closed_at'] < now:
            # for dt_str in get_days_range(issue['closed_at'], 7):
            #     dates[dt_str]['closed_weekly'] += 1
            for dt_str in get_days_range(issue['closed_at'], 28):
                dates[dt_str]['closed_monthly'] += 1
        # for dt_str in get_days_range(issue['created_at'], 7):
        #     dates[dt_str]['opened_weekly'] += 1
        for dt_str in get_days_range(issue['created_at'], 28):
            dates[dt_str]['opened_monthly'] += 1
        
    
    o = []
    for date, label_counts in dates.items():
        o.append(dict(date=date, label_counts=label_counts))
    print json.dumps(o)

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("comment_cache_dir", type=str, default="comment_cache", help="directory to cache comments")
    tornado.options.define("limit", default=None, type=int, help="max number of records to fetch")
    tornado.options.parse_command_line()
    
    assert tornado.options.options.repo
    run()
