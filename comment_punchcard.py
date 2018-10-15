import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import os
import glob
from collections import defaultdict
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
    punchcard = defaultdict(lambda: list([0]*24))
    
    for event in events:
        actor = event['actor']['login']
        hour = _github_dt(event['created_at']).hour
        punchcard[actor][hour]+=1

    print "%15s %s" % ("", " ".join(map(lambda x: "%3d" % x if x else '  -', range(0,24))))
    for actor in sorted(punchcard.keys()):
        print "%15s %s" % (actor, " ".join(map(lambda x: "%3d" % x if x else '  -', punchcard[actor])))

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

    event_summary(events)


if __name__ == "__main__":
    min_dt = datetime.datetime(datetime.datetime.utcnow().year-1,1,1)
    max_dt = datetime.datetime.utcnow()
    
    tornado.options.define("repo", default=None, type=str, help="user/repo to query", multiple=True)
    tornado.options.define("min_dt", default=min_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as start of changelog")
    tornado.options.define("max_dt", default=max_dt.strftime("%Y-%m-%d"), type=str, help="YYYY-MM-DD as end of changelog")
    tornado.options.define("actor", default=None, type=str, help="filter to events for this user")
    tornado.options.define("skip_event_type", default=["labeled", "head_ref_deleted", "referenced", "subscribed", "unassigned", "mentioned"], multiple=True)
    tornado.options.define("cache_base", type=str, default="../repo_cache", help="base cache directory")
    tornado.options.parse_command_line()
    
    o = tornado.options.options
    logging.info('min_dt = %s', o.min_dt)
    assert o.repo
    event_cache_dirs = []
    run(o.repo)
