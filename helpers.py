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
