import urllib2
import urlparse

from .settings import get_setting


class UnexpectedStatusCode(urllib2.HTTPError):

    def __init__(self, resp):
        super(UnexpectedStatusCode, self).__init__(
            resp.url, resp.code, resp.msg, resp.headers, resp.fp)


class HTTPTransport(object):
    """Transport to read and write files over HTTP.

    This transport expects that the target HTTP hosts implements the GET,
    HEAD, PUT and DELETE methods according to RFC2616.
    """
    timeout = get_setting('TIMEOUT')

    def __init__(self, base_url):
        scheme, netloc, path, query, fragment = urlparse.urlsplit(base_url)
        if query or fragment:
            raise ValueError('base_url may not contain a query or fragment.')
        self.scheme = scheme or 'http'
        self.path = path or '/'

    def get_url(self, host, name):
        """Return the full URL for a file on a given host."""
        path = self.path + name
        return urlparse.urlunsplit((self.scheme, host, path, '', ''))

    def content(self, host, name):
        url = self.get_url(host, name)
        resp = urllib2.urlopen(GetRequest(url), timeout=self.timeout)
        length = resp.info().get('Content-Length')
        if length is None:
            return resp.read()
        else:
            return resp.read(int(length))

    def exists(self, host, name):
        url = self.get_url(host, name)
        try:
            resp = urllib2.urlopen(HeadRequest(url), timeout=self.timeout)
            return True                 # server sent a 2xx code, file exists
        except urllib2.HTTPError, e:
            if e.code in (404, 410):    # server says the file doesn't exist
                return False
            raise

    def size(self, host, name):
        url = self.get_url(host, name)
        resp = urllib2.urlopen(HeadRequest(url), timeout=self.timeout)
        length = resp.info().get('Content-Length')
        if length is None:
            raise NotImplementedError("The HTTP server did not provide a"
                    "content length for %r." % resp.geturl())
        return int(length)

    def create(self, host, name, content):
        """Create or update a file with a PUT request.

        Return True if the file existed, False if it did not.
        Raise an urllib2.URLError if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urllib2.urlopen(PutRequest(url, content), timeout=self.timeout)
        if resp.code == 201:
            return False
        elif resp.code == 204:
            return True
        else:
            raise UnexpectedStatusCode(resp)

    def delete(self, host, name):
        """Delete a file with a PUT request.

        Return True if the file existed, False if it did not.
        Raise an urllib2.URLError if something goes wrong.
        """
        url = self.get_url(host, name)
        try:
            resp = urllib2.urlopen(DeleteRequest(url), timeout=self.timeout)
            if resp.code in (200, 202, 204):
                return True
            else:
                raise UnexpectedStatusCode(resp)
        except urllib2.HTTPError, e:
            if e.code in (404, 410):    # server says the file doesn't exist
                return False
            raise


class GetRequest(urllib2.Request):
    def get_method(self):
        return 'GET'


class HeadRequest(urllib2.Request):
    def get_method(self):
        return 'HEAD'


class DeleteRequest(urllib2.Request):
    def get_method(self):
        return 'DELETE'


class PutRequest(urllib2.Request):
    def get_method(self):
        return 'PUT'
