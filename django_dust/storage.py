from threading import Thread
import socket
import random
import urlparse

from django.core.files.base import ContentFile
from django.core.files.storage import Storage, FileSystemStorage
from django.conf import settings
from django.utils.encoding import filepath_to_uri

from . import http
from .settings import get_setting


class DistributionError(IOError):
    pass


class DistributedStorageMixin(object):

    def __init__(self, hosts=None, base_url=None):
        if hosts is None:                                   # cover: disable
            hosts = get_setting('MEDIA_HOSTS')
        self.hosts = hosts
        if base_url is None:                                # cover: disable
            base_url = settings.MEDIA_URL
        self.base_url = base_url
        self.transport = http.HTTPTransport(base_url=self.base_url)

    def _execute(self, action, name, data=None):
        '''
        Runs an operation (put or delete) over several hosts at once in multiple
        threads.
        '''
        def run(index, host):
            try:
                if action == 'PUT':
                    results[index] = self.transport.put(host, name, data)
                elif action == 'DELETE':
                    results[index] = self.transport.delete(host, name)
                else:
                    raise ValueError("Unsupported action %r" % action)
            except Exception, e:
                results[index] = (e)

        # Run distribution threads keeping result of each operation in `results`.
        results = [None] * len(self.hosts)
        threads = [Thread(target=run, args=(index, h)) for index, h in enumerate(self.hosts)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        exceptions = []
        for host, result in zip(self.hosts, results):
            if result is None: # no errors, remember successful_host to use in retries
                successful_host = host
                break
        else:
            successful_host = None

        # All `socket.error` exceptions are not fatal meaning that a host might
        # be temporarily unavailable. Those operations are kept in a queue in
        # database to be retried later.
        # All other errors mean in most cases misconfigurations and are fatal
        # for the whole distributed operation.
        for host, result in zip(self.hosts, results):
            if isinstance(result, socket.error):
                if successful_host is not None:
                    # TODO: retry code removed from here
                    pass
                else:
                    exceptions.append(result)
            elif isinstance(result, Exception):
                exceptions.append(result)
        if exceptions:
            raise DistributionError(*exceptions)

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        # Allowing writes would be doable, if we distribute the file to the
        # media servers when it's closed. Let's forbid it for now.
        if mode != 'rb':
            raise IOError('Unsupported mode %r, use %r.' % (mode, 'rb'))

    def _save(self, name, content):
        # It's hard to avoid buffering the whole file in memory,
        # because different threads will read it simultaneously.
        self._execute('PUT', name, content.read())

    # The implementations of get_valid_name, get_available_name, path and url
    # in Storage and FileSystemStorage are OK for DistributedStorage and
    # HybridStorage.

    ### Mandatory methods

    def delete(self, name):
        self._execute('DELETE', name, [])

    def exists(self, name):
        return self.transport.exists(random.choice(self.hosts), name)

    # It is not possible to implement listdir over pure HTTP. It could
    # be done with WebDAV.

    def size(self, name):
        return self.transport.size(random.choice(self.hosts), name)

    def url(self, name):
        return urlparse.urljoin(self.base_url, filepath_to_uri(name))


class DistributedStorage(DistributedStorageMixin, Storage):

    def __init__(self, hosts=None, base_url=None):
        DistributedStorageMixin.__init__(self, hosts, base_url)
        Storage.__init__(self)

    ### Hooks for custom storage objects

    def _open(self, name, mode='rb'):
        DistributedStorageMixin._open(self, name, mode)     # just a check
        host = random.choice(self.hosts)
        return ContentFile(self.transport.get(host, name))

    def _save(self, name, content):
        # This is really prone to race conditions - see README.
        name = self.get_available_name(name)
        DistributedStorageMixin._save(self, name, content)
        return name


class HybridStorage(DistributedStorageMixin, FileSystemStorage):

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
        # media servers. This could be wrong if a DELETE for this file name
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
