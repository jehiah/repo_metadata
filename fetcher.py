import json
import tornado.httpclient
import tornado.options
import logging
import platform
import tornado

from helpers import get_link

_user_agent = "python/%(python_version)s tornadoweb/%(tornado_version)s (https://github.com/jehiah/repo_metadata)" % dict(
    python_version=platform.python_version(),
    tornado_version=tornado.version,
)


def fetch_one(url):
    http = tornado.httpclient.HTTPClient()
    resp = http.fetch(url, user_agent=_user_agent, headers=github_auth_headers())
    return json.loads(resp.body)
    

def github_auth_headers(headers=None):
    headers = headers or {}
    token = tornado.options.options.access_token
    assert token
    headers['Authorization'] = "token %s" % token
    return headers


def fetch_all(url, limit=None, headers=None, callback=None):
    o = []
    headers = headers or {}
    http = tornado.httpclient.HTTPClient()
    for x in range(300):
        try:
            resp = http.fetch(url, user_agent=_user_agent, headers=github_auth_headers(headers))
        except tornado.httpclient.HTTPError, e:
            logging.error('failed %r %r', e.response.body, e.response)
            raise e
        data = json.loads(resp.body)
        logging.info('got %d records', len(data))
        logging.debug('%r', data)
        next_url = get_link(resp, 'next')
        o.extend(data)
        if callback:
            callback(data)
        if limit and len(o) > limit:
            logging.info('%d is passed limit of %d', len(o), limit)
            break
        if next_url:
            url = next_url
        else:
            break
    return o
