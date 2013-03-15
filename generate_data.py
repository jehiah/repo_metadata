import tornado.httpclient
import tornado.options
import simplejson as json
import logging
import urllib
from collections import defaultdict
import datetime

endpoint = "https://api.github.com/repos/%s/issues?"

# return start, end, [labels]
def get_issue_data(issue):
    created_at = datetime.datetime.strptime( issue["created_at"], "%Y-%m-%dT%H:%M:%SZ" )
    if issue['state'] == 'closed':
        closed_at = datetime.datetime.strptime( issue["closed_at"], "%Y-%m-%dT%H:%M:%SZ" )
    else:
        closed_at = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    return dict(created_at=created_at, closed_at=closed_at, labels=issue['labels'])
    
def get_link(req, key="next"):
    links = req.headers.get('Link')
    for link in links.split(', '):
        url, rel = link.split('; ')
        url = url.strip('<>')
        assert rel.startswith("rel=")
        rel = rel[4:].strip('"')
        if rel == key:
            return url

def fetch_all(url):
    o = []
    http = tornado.httpclient.HTTPClient()
    for x in range(80):
        resp = http.fetch(url)
        data = json.loads(resp.body)
        logging.debug('got %d records', len(data))
        next_url = get_link(resp, 'next')
        o.extend(data)
        if next_url:
            url = next_url
        else:
            break
    return o

def get_issue_days(issue):
    delta = issue['closed_at'] - issue['created_at']
    for x in range(delta.days):
        dt = issue['created_at'] + datetime.timedelta(days=x)
        yield dt.strftime('%Y-%m-%d')

def run():
    global endpoint
    token = tornado.options.options.access_token
    endpoint = endpoint % tornado.options.options.repo
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, filter='all', state='closed'))
    raw_issues = fetch_all(url)
    url = endpoint + urllib.urlencode(dict(access_token=token, per_page=100, filter='all', state='open'))
    raw_issues += fetch_all(url)
    logging.debug(len(raw_issues))
    issue_data = [get_issue_data(x) for x in raw_issues]
    
    def newrow():
        return defaultdict(int)
    
    dates = defaultdict(newrow)
    for issue in issue_data:
        for date in get_issue_days(issue):
            dates[date]['all'] += 1
            for label in issue['labels']:
                dates[date][label['name']] += 1
    
    o = []
    for date, label_counts in dates.items():
        o.append(dict(date=date, label_counts=label_counts))
    print json.dumps(o)

if __name__ == "__main__":
    tornado.options.define("repo", default=None, type=str, help="user/repo to query")
    tornado.options.define("access_token", type=str, default=None, help="github access_token")
    tornado.options.parse_command_line()
    
    run()
