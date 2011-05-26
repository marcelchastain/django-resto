import random
import threading
import urllib2
import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, FileSystemStorage
from django.utils.encoding import filepath_to_uri

from .settings import get_setting


class UnexpectedStatusCode(urllib2.HTTPError):

    """Exception raised when a server returns an unexpected status code.

    Only the most common codes (200, 201, 204, 404) are interpreted by
    DefaultTransport. If it receives another code, it will raise this
    exception. It won't try to interpret the class of the status code.

    For instance, "202 Accepted" indicates a successful request, but it
    breaks our expectation that the upload is synchronous. So we'd better
    raise an exception. Other uncommon codes pose similar problems.
    """

    def __init__(self, resp):
        super(UnexpectedStatusCode, self).__init__(
            resp.url, resp.code, resp.msg, resp.headers, resp.fp)


class GetRequest(urllib2.Request):
    """HTTP GET request."""
    # This adds nothing to urllib2, but it's there for consistency.
    def get_method(self):
        return 'GET'


class HeadRequest(urllib2.Request):
    """HTTP HEAD request."""
    def get_method(self):
        return 'HEAD'


class DeleteRequest(urllib2.Request):
    """HTTP DELETE request."""
    def get_method(self):
        return 'DELETE'


class PutRequest(urllib2.Request):
    """HTTP PUT request."""
    def get_method(self):
        return 'PUT'


class DefaultTransport(object):
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
        """Return the full URL for a file on a given host (internal use)."""
        path = self.path + name
        return urlparse.urlunsplit((self.scheme, host, path, '', ''))

    def content(self, host, name):
        """Get the content of a file as a string.

        urllib2.URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urllib2.urlopen(GetRequest(url), timeout=self.timeout)
        length = resp.info().get('Content-Length')
        if length is None:
            return resp.read()
        else:
            return resp.read(int(length))

    def exists(self, host, name):
        """Check if a file exists.

        Return True if the file exists, False if it doesn't.

        urllib2.URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        try:
            resp = urllib2.urlopen(HeadRequest(url), timeout=self.timeout)
            return True                 # server sent a 2xx code, file exists
        except urllib2.HTTPError, e:
            if e.code in (404, 410):    # server says the file doesn't exist
                return False
            raise

    def size(self, host, name):
        """Check the size of a file.

        This method relies on the Content-Length header.

        urllib2.URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urllib2.urlopen(HeadRequest(url), timeout=self.timeout)
        length = resp.info().get('Content-Length')
        if length is None:
            raise NotImplementedError("The HTTP server did not provide a"
                    "content length for %r." % resp.geturl())
        return int(length)

    def create(self, host, name, content):
        """Create or update a file.

        Return True if the file existed, False if it did not.

        urllib2.URLError will be raised if something goes wrong.
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
        """Delete a file.

        Return True if the file existed, False if it did not.

        urllib2.URLError will be raised if something goes wrong.
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


class DistributedStorageMixin(object):

    """Mixin for storage backends that distribute files on several servers."""

    def __init__(self, hosts=None, base_url=None):
        if hosts is None:                                   # cover: disable
            hosts = get_setting('MEDIA_HOSTS')
        self.hosts = hosts
        if base_url is None:                                # cover: disable
            base_url = settings.MEDIA_URL
        self.base_url = base_url
        self.transport = DefaultTransport(base_url=self.base_url)

    def execute_parallel(self, func, *args):
        """Run an action over several hosts in parallel.

        For each host, this will call func(host, *args).
        """
        exceptions = {}
        def execute_one(host):
            try:
                func(host, *args)
            except Exception, exc:
                exceptions[host] = exc

        threads = [threading.Thread(target=execute_one, args=(host,)) for host in self.hosts]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for exception in exceptions:
            # TODO logging
            pass

        if exceptions and self.fatal_exceptions:
            # Let's raise the first exception, we've logged them all anyway
            raise exceptions[0]

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        # Allowing writes would be doable, if we distribute the file to the
        # media servers when it's closed. Let's forbid it for now.
        if mode != 'rb':
            raise IOError('Unsupported mode %r, use %r.' % (mode, 'rb'))

    def _save(self, name, content):
        # It's hard to avoid buffering the whole file in memory,
        # because different threads will read it simultaneously.
        self.execute_parallel(self.transport.create, name, content.read())

    # The implementations of get_valid_name, get_available_name, path and url
    # in Storage and FileSystemStorage are OK for DistributedStorage and
    # HybridStorage.

    ### Mandatory methods

    def delete(self, name):
        self.execute_parallel(self.transport.delete, name)

    def exists(self, name):
        return self.transport.exists(random.choice(self.hosts), name)

    # It is not possible to implement listdir in pure HTTP. It could
    # be done with WebDAV.

    def size(self, name):
        return self.transport.size(random.choice(self.hosts), name)

    def url(self, name):
        return urlparse.urljoin(self.base_url, filepath_to_uri(name))


class DistributedStorage(DistributedStorageMixin, Storage):

    """Backend that stores files remotely over HTTP."""

    def __init__(self, hosts=None, base_url=None):
        DistributedStorageMixin.__init__(self, hosts, base_url)
        Storage.__init__(self)

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        DistributedStorageMixin._open(self, name, mode)     # just a check
        host = random.choice(self.hosts)
        return ContentFile(self.transport.content(host, name))

    def _save(self, name, content):
        # This is really prone to race conditions - see README.
        name = self.get_available_name(name)
        DistributedStorageMixin._save(self, name, content)
        return name


class HybridStorage(DistributedStorageMixin, FileSystemStorage):

    """Backend that stores files both locally and remotely over HTTP."""

    def __init__(self, hosts=None, base_url=None, location=None):
        DistributedStorageMixin.__init__(self, hosts, base_url)
        FileSystemStorage.__init__(self, location, base_url)

    # Read operations can be done with FileSystemStorage. Write operations
    # must be done with FileSystemStorage and DistributedStorageMixin, in
    # this order.

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        DistributedStorageMixin._open(self, name, mode)     # just a check
        return FileSystemStorage._open(self, name, mode)

    def _save(self, name, content):
        name = FileSystemStorage._save(self, name, content)
        content.seek(0)
        # After this line, we will assume that 'name' is available on the
        # media servers. This could be wrong if a delete for this file name
        # failed at some point in the past.
        DistributedStorageMixin._save(self, name, content)
        return name

    ### Mandatory methods

    def delete(self, name):
        FileSystemStorage.delete(self, name)
        DistributedStorageMixin.delete(self, name)

    def exists(self, name):
        return FileSystemStorage.exists(self, name)

    def listdir(self, name):
        return FileSystemStorage.listdir(self, name)

    def size(self, name):
        return FileSystemStorage.size(self, name)
