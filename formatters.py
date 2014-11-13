import datetime

def _github_dt(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
