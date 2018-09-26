import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import glob
from collections import defaultdict
from operator import itemgetter
import datetime

from formatters import _github_dt
from helpers import cache_dir

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


def is_filtered_out(event, min_dt, max_dt):
    issue_number = event.get('issue',{}).get('number')
    if not issue_number:
        logging.warning('no issue number in %r', event)
        return True
    
    dt = _github_dt(event['created_at'])
    if dt < min_dt:
        return True
    if dt > max_dt:
        return True
    
    if not _is_event_related(event, tornado.options.options.actor):
        return True

    if tornado.options.options.skip_event_type and event['event'] in tornado.options.options.skip_event_type:
        return True

    return False

def event_summary(events):
    issues = defaultdict(list)
    for event in events:
        logging.debug('%s', event)
        issue_number = event.get('issue',{}).get('number')
        
        d = dict(
            dt=_github_dt(event['created_at']),
            action=event['event'],
            actor=event['actor']['login'],
            issue_number=issue_number,
            issue_state=event['issue']['state'],
            title=event['issue']['title'],
            sort_key = event['issue']['title'].split()[0],
            state=event['issue']['state'],
            labels=[x['name'] for x in event['issue']['labels']],
            html_url=event['issue']['html_url'],
            repo='/'.join(event['issue']['repository_url'].split('/')[-2:]),
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
        repo =  data[0]['repo']
        if repo == tornado.options.options.repo[0]:
            repo = ''
        if state == "OPEN" and "RFR" in data[0]['labels']:
            state = "RFR"
        if state == "CLOSED" and "merged" in actions:
            state = "MERGED"
        if state == "OPEN" and "WIP" in title:
            state = "WIP"
        print " * [%s#%s](%s) %s %s" % (repo, issue_number, data[0]['html_url'], state, title)

def run(repos):
    o = tornado.options.options
    min_dt = datetime.datetime.strptime(o.min_dt, '%Y-%m-%d')
    max_dt = datetime.datetime.strptime(o.max_dt, '%Y-%m-%d').replace(hour=23, minute=59)

    events = []
    for repo in repos:
        assert repo and "/" in repo
        dirname = cache_dir(o.cache_base, "event_cache", repo)
        for event_file in glob.glob(os.path.join(dirname, '*.json')):
            with open(event_file, 'r') as f:
                event_data = json.load(f)
                if is_filtered_out(event_data, min_dt, max_dt):
                    continue
                events.append(event_data)
    
    dates = [_github_dt(event['created_at']) for event in events]
    logging.info("%d events from %s to %s", len(events), min(dates), max(dates))

    print "---"
    print ""
    print "**PR ChangeLog (from %s to %s)**" % (min_dt.strftime('%Y-%m-%d %A'), max_dt.strftime('%Y-%m-%d %A'))
    print ""
    event_summary(events)


if __name__ == "__main__":
    min_dt = datetime.datetime.utcnow().replace(hour=0,minute=0)
    if min_dt.isoweekday() < 3:
        min_dt -= datetime.timedelta(days=7)
    min_dt -= datetime.timedelta(days=min_dt.isoweekday()-1)
    max_dt = datetime.datetime.utcnow()
    
    tornado.options.define("repo", default=None, type=str, help="user/repo to query", multiple=True)
    tornado.options.define("min_dt", default=min_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as start of changelog")
    tornado.options.define("max_dt", default=max_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as end of changelog")
    tornado.options.define("actor", default=None, type=str, help="filter to events for this user")
    tornado.options.define("skip_event_type", default=["labeled", "head_ref_deleted", "referenced", "subscribed", "unassigned"], multiple=True)
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    logging.info('min_dt = %s', o.min_dt)
    assert o.repo
    event_cache_dirs = []
    run(o.repo)
