"""
Copyright (c) F5, Inc.

This source code is licensed under the Apache License Version 2.0 found in the
LICENSE file in the root directory of this source tree.

House general URL tools useful for manipulating urllib3.util.Url objects.
"""

import pathlib
import urllib

import urllib3


def add_to_url(url, **defined_attributes):
    """Modify to the url to include the given attributes."""
    if not isinstance(url, urllib3.util.url.Url):
        url = parse_url(url)
    attributes = dict(
        scheme=defined_attributes.get("scheme", url.scheme),
        host=defined_attributes.get("host", url.host),
        port=defined_attributes.get("port", url.port),
        path=defined_attributes.get("path", url.path),
        query=defined_attributes.get("query", url.query),
        fragment=defined_attributes.get("fragment", url.fragment),
    )
    url = urllib3.util.url.Url(**attributes)
    return url.url


def get_host_from(url):
    """Get the host definition from the URL given."""
    if not isinstance(url, urllib3.util.Url):
        url = parse_url(url)
    return url.host


def get_path_from_url(url):
    """Get just the url path as a string from the given url.

    Gets from a ``urllib3.util.url.Url`` or str the path of the url given as a string.
    """
    if not isinstance(url, urllib3.util.url.Url):
        url = parse_url(url)
    return "" if url.path is None else url.path


def join_url(base, *uri, preserve_base=True, scheme=False):
    """Return the concatenation of base and url.

    preserve_base:bool:True:
        specifies whether the last substring after the last '/' is preserved
    scheme:bool:True:
        specifies that the given base has a scheme that should be kept as-is even if it
        is not http|https
        (e.g. ``ssh:``)

    The 'preserve_base' option is a requirement to match CurlRequst.join_url.
    """
    url = urllib3.util.url.parse_url(base)
    if isinstance(url.path, (bytes, str)):
        path = pathlib.PosixPath(url.path)
    else:
        path = pathlib.PosixPath("/")
    path = path.joinpath(*uri)
    if preserve_base and len(uri) and uri[-1].endswith("/"):
        path = f"{path}/"
    if url is not None:
        return urllib3.util.url.Url(
            scheme=url.scheme,
            host=url.host,
            path=str(path),
            query=url.query,
            fragment=url.fragment,
            port=url.port,
        ).url
    return str(path)


def parse_url(str_url):
    """Get the parsed URL object.

    Gets a ``urllib3.util.Url`` object in a uniform way such that if an unpredictable
    security issue around parsing URL's is discovered against ``urllib3``, it's utils, etc.
    then the pain of updating is minimal.  Also looking at the in-progress ``urllib4``.
    """
    return urllib3.util.parse_url(str_url)


def quote_url_path(url, safe="/"):
    """Return url with path component quoted."""
    scheme, netloc, path, qs, fragment = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(path, safe=safe).replace("%25", "%2525")
    return urllib.parse.urlunsplit((scheme, netloc, path, qs, fragment))
