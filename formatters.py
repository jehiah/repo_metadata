import datetime

def _github_dt(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")

def github_dt_str(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")