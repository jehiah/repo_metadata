import os.path
import logging

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

def cache_dir(base, cache_type, repo):
    repo_dir = repo.replace("/", "_")
    dirname = os.path.join(base, cache_type, repo_dir)
    if not os.path.exists(dirname):
        logging.info("mkdir %s", dirname)
        os.makedirs(dirname)
    return dirname
    