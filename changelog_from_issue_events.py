import tornado.httpclient
import tornado.options
import simplejson as json
import logging
# import os
# import glob
import urllib
from collections import defaultdict
from operator import itemgetter
import datetime

from formatters import _github_dt


endpoint = "https://api.github.com/repos/%s/issues/events?"
now = datetime.datetime.utcnow()
  
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
        # headers = {"Content-Type":"application/vnd.github-commitcomment.full+json"}
        headers = {}
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
        # cache_comments(data)
        if limit and len(o) > limit:
            logging.info('%d is passed limit of %d', len(o), limit)
            break
        if next_url:
            url = next_url
        else:
            break
    return o

def event_summary(events):
    issues = defaultdict(list)
    for event in events:
        issue_number = event.get('issue',{}).get('number')
        if not issue_number:
            logging.warning('no issue number in %r', event)
            continue
        
        if tornado.options.options.actor and event['actor']['login'] != tornado.options.options.actor:
            continue
        if event['event'] in tornado.options.options.skip_event_type:
            continue
        
        d = dict(
            dt=_github_dt(event['created_at']),
            action=event['event'],
            actor=event['actor']['login'],
            issue_number=issue_number,
            issue_state=event['issue']['state'],
            title=event['issue']['title'],
        )
        issues[issue_number].append(d)

    for issue_number, data in issues.items():
        data.sort(key=itemgetter('dt'))
        title = data[0]['title']
        states =  ", ".join([x['action'] for x in data])
        print " * [#%s](https://github.com/%s/issues/%s) %s (%s)" % (issue_number, tornado.options.options.repo, issue_number, title, states)

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, direction="desc", sort="created"))
    logging.info('fetching events for %r', tornado.options.options.repo)
    raw_events = fetch_all(url, limit=tornado.options.options.limit)
    logging.debug(len(raw_events))
    event_summary(raw_events)


if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("comment_cache_dir", type=str, default="comment_cache", help="directory to cache comments")
    tornado.options.define("limit", default=None, type=int, help="max number of records to fetch")
    tornado.options.define("timerange", default=14, type=int, help="max number of (recent) days to generate a summary for")
    tornado.options.define("actor", default=None, type=str, help="filter to events for this user")
    tornado.options.define("skip_event_type", default=["labeled", "head_ref_deleted", "referenced", "subscribed"], multiple=True)
    tornado.options.parse_command_line()
    
    assert tornado.options.options.repo
    run()
