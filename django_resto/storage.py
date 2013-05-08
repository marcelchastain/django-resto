from __future__ import unicode_literals

import logging
import random
import sys
import threading
try:
    from urllib.parse import quote, urljoin, urlsplit, urlunsplit
    from urllib.request import HTTPError, Request, URLError, urlopen
except ImportError:
    from urllib import quote
    from urllib2 import HTTPError, Request, URLError, urlopen
    from urlparse import urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, FileSystemStorage
from django.utils.encoding import filepath_to_uri

from .settings import get_setting


logger = logging.getLogger(__name__)


class UnexpectedStatusCode(HTTPError):

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


class GetRequest(Request):
    """HTTP GET request."""
    # This adds nothing to urllib, but it's there for consistency.
    def get_method(self):
        return 'GET'


class HeadRequest(Request):
    """HTTP HEAD request."""
    def get_method(self):
        return 'HEAD'


class DeleteRequest(Request):
    """HTTP DELETE request."""
    def get_method(self):
        return 'DELETE'


class PutRequest(Request):
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
        scheme, netloc, path, query, fragment = urlsplit(base_url)
        if query or fragment:
            raise ValueError('base_url may not contain a query or fragment.')
        self.scheme = scheme or 'http'
        self.path = path or '/'

    def get_url(self, host, name):
        """Return the full URL for a file on a given host (internal use)."""
        path = self.path + quote(name.encode('utf-8'))
        return urlunsplit((self.scheme, host, path, '', ''))

    def content(self, host, name):
        """Get the content of a file as a string.

        URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urlopen(GetRequest(url), timeout=self.timeout)
        if resp.code != 200:
            raise UnexpectedStatusCode(resp)
        length = resp.info().get('Content-Length')
        if length is None:                                  # cover: disable
            return resp.read()
        else:
            return resp.read(int(length))

    def exists(self, host, name):
        """Check if a file exists.

        Return True if the file exists, False if it doesn't.

        URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        try:
            resp = urlopen(HeadRequest(url), timeout=self.timeout)
            if resp.code != 200:
                raise UnexpectedStatusCode(resp)
            return True
        except HTTPError as e:
            if e.code not in (404, 410):
                raise
            return False

    def size(self, host, name):
        """Check the size of a file.

        This method relies on the Content-Length header.

        URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urlopen(HeadRequest(url), timeout=self.timeout)
        if resp.code != 200:
            raise UnexpectedStatusCode(resp)
        length = resp.info().get('Content-Length')
        if length is None:
            raise NotImplementedError("The HTTP server did not provide a"
                    "content length for %r." % resp.geturl())
        return int(length)

    def create(self, host, name, content):
        """Create or update a file.

        Return True if the file existed, False if it did not.

        URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        resp = urlopen(PutRequest(url, content), timeout=self.timeout)
        if resp.code == 201:
            return False
        elif resp.code == 204:
            logger.warning("PUT on existing file %s on %s.", name, host)
            return True
        else:
            raise UnexpectedStatusCode(resp)

    def delete(self, host, name):
        """Delete a file.

        Return True if the file existed, False if it did not.

        URLError will be raised if something goes wrong.
        """
        url = self.get_url(host, name)
        try:
            resp = urlopen(DeleteRequest(url), timeout=self.timeout)
            if resp.code not in (200, 204):
                raise UnexpectedStatusCode(resp)
            return True
        except HTTPError as e:
            if e.code not in (404, 410):
                raise
            logger.warning("DELETE on missing file %s on %s.", name, host)
            return False


class DistributedStorageMixin(object):

    """Mixin for storage backends that distribute files on several servers."""

    fatal_exceptions = get_setting('FATAL_EXCEPTIONS')
    show_traceback = get_setting('SHOW_TRACEBACK')

    def __init__(self, hosts=None, base_url=None):
        if hosts is None:                                   # cover: disable
            hosts = get_setting('MEDIA_HOSTS')
        self.hosts = hosts
        if base_url is None:                                # cover: disable
            base_url = settings.MEDIA_URL
        self.base_url = base_url
        self.transport = DefaultTransport(base_url=self.base_url)

    def execute(self, func, url, *args, **kwargs):
        """Run an action over several hosts in parallel."""
        exceptions = {}

        def execute_inner(host):
            try:
                func(host, url, *args, **kwargs)
            except Exception:
                exceptions[host] = sys.exc_info()

        if len(self.hosts) == 1:
            execute_inner(self.hosts[0])
        else:
            threads = [threading.Thread(target=execute_inner, args=(host,))
                    for host in self.hosts]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        for host, exc_info in exceptions.items():
            action = func.__name__
            logger.error("Failed to %s %s on %s.", action, url, host,
                    exc_info=exc_info if self.show_traceback else None)

        if exceptions and self.fatal_exceptions:
            # Let's raise a random exception, we've logged them all anyway
            raise exceptions.popitem()[1][1]


class DistributedStorage(DistributedStorageMixin, Storage):

    """Backend that stores files remotely over HTTP."""

    def __init__(self, hosts=None, base_url=None):
        DistributedStorageMixin.__init__(self, hosts, base_url)
        if not self.fatal_exceptions:
            logger.warning("You're using the DistributedStorage backend with "
                    "RESTO_FATAL_EXCEPTIONS = %r.", self.fatal_exceptions)
            logger.warning("This is prone to data-loss problems, and I won't "
                    "take any responsibility in what happens from now on.")
            logger.warning("You have been warned.")
        Storage.__init__(self)

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        # Allowing writes would be doable, if we distribute the file to the
        # media servers when it's closed. Let's forbid it for now.
        if mode != 'rb':
            raise IOError('Unsupported mode %r, use %r.' % (mode, 'rb'))
        host = random.choice(self.hosts)
        try:
            return ContentFile(self.transport.content(host, name))
        except URLError:
            logger.error("Failed to download %s from %s.", name, host,
                    exc_info=self.show_traceback)
            raise

    def _save(self, name, content):
        # It's hard to avoid buffering the whole file in memory,
        # because different threads will read it simultaneously.
        self.execute(self.transport.create, name, content.read())
        return name

    ### Mandatory methods

    # The implementations of get_valid_name, get_available_name, and path
    # in Storage are OK for DistributedStorage.

    def delete(self, name):
        self.execute(self.transport.delete, name)

    def exists(self, name):
        host = random.choice(self.hosts)
        try:
            return self.transport.exists(host, name)
        except URLError:
            logger.error("Failed to check if %s exists on %s.", name, host,
                    exc_info=self.show_traceback)
            raise

    # It is not possible to implement listdir in pure HTTP. It could
    # be done with WebDAV.

    def size(self, name):
        host = random.choice(self.hosts)
        try:
            return self.transport.size(host, name)
        except URLError:
            logger.error("Failed to get the size of %s from %s.", name, host,
                    exc_info=self.show_traceback)
            raise

    def url(self, name):
        return urljoin(self.base_url, filepath_to_uri(name))


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
        # Writing is forbidden, see DistributedStorage._open.
        if mode != 'rb':
            raise IOError('Unsupported mode %r, use %r.' % (mode, 'rb'))
        return FileSystemStorage._open(self, name, mode)

    def _save(self, name, content):
        name = FileSystemStorage._save(self, name, content)
        # After this line, we will assume that 'name' is available on the
        # media servers. This could be wrong if a delete for this file name
        # failed at some point in the past.
        self.execute(self.upload, name)
        return name

    # Make this a separate method so it can be passed to a task queue.
    def upload(self, host, name):
        with self.open(name) as handle:
            self.transport.create(host, name, handle.read())

    ### Mandatory methods

    # The implementations of get_valid_name, get_available_name, path, exists,
    # listdir, size, and url in FileSystemStorage are OK for HybridStorage.

    def delete(self, name):
        FileSystemStorage.delete(self, name)
        self.execute(self.transport.delete, name)


class AsyncStorage(HybridStorage):

    """Backend that stores files both locally and remotely over HTTP."""

    def execute(self, func, url, *args, **kwargs):
        """Run an action over several hosts asynchronously."""
        for host in self.hosts:
            self.execute_one(func, host, url, *args, **kwargs)

    def execute_one(self, func, host, url, *args, **kwargs):
        """Run a single action asynchronously."""
        def execute_inner():
            # Insert a delay here to actually test the asynchronous behavior.
            try:
                func(host, url, *args, **kwargs)
            except Exception:
                action = func.__name__
                logger.error("Failed to %s %s on %s.", action, url, host,
                        exc_info=self.show_traceback)
        return threading.Thread(target=execute_inner).start()
