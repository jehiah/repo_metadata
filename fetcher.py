import json
import tornado.httpclient
import logging

from helpers import get_link

def fetch_all(url, limit=None, headers=None, callback=None):
    o = []
    headers = headers or {}
    http = tornado.httpclient.HTTPClient()
    for x in range(80):
        try:
            resp = http.fetch(url, user_agent='issue fetcher (tornado/httpclient)', headers=headers)
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
