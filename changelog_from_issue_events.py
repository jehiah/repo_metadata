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

def _is_event_related(event, actor):
    if not actor:
        return True
    # if event['actor']['login'] == actor:
    #     return True
    issue = event.get('issue') or {}
    if (issue.get('assignee') or {}).get('login') == actor:
        return True
    if (issue.get('user') or {}).get('login') == actor:
        return True
    return False

def event_summary(events, min_dt, max_dt):
    issues = defaultdict(list)
    for event in events:
        issue_number = event.get('issue',{}).get('number')
        if not issue_number:
            logging.warning('no issue number in %r', event)
            continue
        
        dt = _github_dt(event['created_at'])
        if dt < min_dt:
            continue
        if dt > max_dt:
            continue
        
        if not _is_event_related(event, tornado.options.options.actor):
            continue

        if tornado.options.options.skip_event_type and event['event'] in tornado.options.options.skip_event_type:
            continue
        
        d = dict(
            dt=dt,
            action=event['event'],
            actor=event['actor']['login'],
            issue_number=issue_number,
            issue_state=event['issue']['state'],
            title=event['issue']['title'],
            sort_key = event['issue']['title'].split()[0],
            state=event['issue']['state'],
            labels=[x['name'] for x in event['issue']['labels']],
        )
        issues[issue_number].append(d)
        # put oldest first
        issues[issue_number].sort(key=itemgetter('dt'), reverse=True)

    sorted_date = sorted([[e[0]['sort_key'], i, e] for i, e in issues.items()])

    for sort_key, issue_number, data in sorted_date:
        # print "%s %r" % (issue_number, map(str, [e['dt'] for e in data]))
        title = data[0]['title']
        actions = [x['action'] for x in data]
        state = data[0]['state'].upper()
        if state == "OPEN" and "RFR" in data[0]['labels']:
            state = "RFR"
        if state == "CLOSED" and "merged" in actions:
            state = "MERGED"
        print " * [#%s](https://github.com/%s/issues/%s) %s %s" % (issue_number, tornado.options.options.repo, issue_number, state, title)

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, direction="desc", sort="created"))
    logging.info('fetching events for %r', tornado.options.options.repo)
    raw_events = fetch_all(url, limit=tornado.options.options.limit)
    date_ranges = [_github_dt(event['created_at']) for event in raw_events]
    min_dt = datetime.datetime.strptime(tornado.options.options.min_dt, '%Y-%m-%d')
    max_dt = datetime.datetime.strptime(tornado.options.options.max_dt, '%Y-%m-%d').replace(hour=23, minute=59)

    logging.info("%d events from %s to %s", len(raw_events), min(date_ranges), max(date_ranges))
    print "---"
    print ""
    print "**PR ChangeLog (from %s to %s)**" % (min_dt.strftime('%Y-%m-%d %A'), max_dt.strftime('%Y-%m-%d %A'))
    print ""
    event_summary(raw_events, min_dt, max_dt)


if __name__ == "__main__":
    min_dt = datetime.datetime.utcnow().replace(hour=0,minute=0)
    if min_dt.isoweekday() < 3:
        min_dt -= datetime.timedelta(days=7)
    min_dt -= datetime.timedelta(days=min_dt.isoweekday()-1)
    max_dt = datetime.datetime.utcnow()
    
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.define("limit", default=1100, type=int, help="max number of records to fetch")
    tornado.options.define("min_dt", default=min_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as start of changelog")
    tornado.options.define("max_dt", default=max_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as end of changelog")
    tornado.options.define("actor", default=None, type=str, help="filter to events for this user")
    tornado.options.define("skip_event_type", default=["labeled", "head_ref_deleted", "referenced", "subscribed"], multiple=True)
    tornado.options.parse_command_line()
    
    logging.info('min_dt = %s', tornado.options.options.min_dt)
    
    assert tornado.options.options.repo
    run()
