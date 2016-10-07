import datetime

def _github_dt(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")

def github_dt_str(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")

def _dt(ts):
    if isinstance(ts, (str, unicode)):
        ts = int(ts)
    return datetime.datetime.utcfromtimestamp(ts)

def _utf8(s):
    """encode a unicode string as utf-8"""
    if isinstance(s, unicode):
        return s.encode("utf-8")
    assert isinstance(s, str)
    return s
