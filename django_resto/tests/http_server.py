from __future__ import unicode_literals

import os.path
import threading
try:
    from urllib.request import URLError, urlopen
except ImportError:
    from urllib2 import URLError, urlopen


from django.conf import settings
from django.utils import unittest

from ..http_server import TestHttpServer
from ..storage import GetRequest, HeadRequest, DeleteRequest, PutRequest


class HttpServerTestCaseMixin(object):

    host = 'localhost'
    port = 4080
    filename = 'test.txt'
    path = '/' + filename
    url = 'http://%s:%d%s' % (host, port, path)
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    num_threads = 1

    def setUp(self):
        super(HttpServerTestCaseMixin, self).setUp()
        self.http_server = TestHttpServer(self.host, self.port)
        self.thread = threading.Thread(target=self.http_server.run)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        self.http_server.stop()
        self.thread.join()
        self.http_server.server_close()
        super(HttpServerTestCaseMixin, self).tearDown()

    def assertHttpSuccess(self, *args):
        return urlopen(*args).read()            # URLError not raised.

    def assertHTTPErrorCode(self, code, *args):
        with self.assertRaises(URLError) as context:
            urlopen(*args)
        self.assertEqual(context.exception.code, code, 'Expected HTTP %d, '
                'got HTTP %d' % (code, context.exception.code))

    def sync(self):
        pass

    def assertServerLogIs(self, log):
        self.sync()
        self.assertEqual(log, self.http_server.log)

    assertEachServerLogIs = assertServerLogIs

    assertAnyServerLogIs = assertServerLogIs


class ExtraHttpServerTestCaseMixin(object):

    num_threads = 2

    def setUp(self):
        super(ExtraHttpServerTestCaseMixin, self).setUp()
        self.alt_http_server = TestHttpServer(self.host, self.port + 1)
        self.alt_thread = threading.Thread(target=self.alt_http_server.run)
        self.alt_thread.daemon = True
        self.alt_thread.start()
        self.alt_url = 'http://%s:%d/' % (self.host, self.port + 1)

    def tearDown(self):
        self.alt_http_server.stop()
        self.alt_thread.join()
        self.alt_http_server.server_close()
        super(ExtraHttpServerTestCaseMixin, self).tearDown()

    def assertAltServerLogIs(self, log):
        self.sync()
        self.assertEqual(log, self.alt_http_server.log)

    def assertEachServerLogIs(self, log):
        self.sync()
        self.assertServerLogIs(log)
        self.assertAltServerLogIs(log)

    def assertAnyServerLogIs(self, log):
        self.sync()
        return search_merge(log, self.http_server.log, self.alt_http_server.log)


def search_merge(log, log1, log2):
    if log == []:
        return log1 == log2 == []
    if log1 == []:
        return log == log2
    if log2 == []:
        return log == log1
    return (
        (log[0] == log1[0] and search_merge(log[1:], log1[1:], log2))
        or
        (log[0] == log2[0] and search_merge(log[1:], log1, log2[1:]))
    )


class HttpServerTestCase(HttpServerTestCaseMixin, unittest.TestCase):

    def test_get(self):
        self.assertHTTPErrorCode(404, GetRequest(self.url))
        self.http_server.create_file(self.filename, b'test')
        body = self.assertHttpSuccess(GetRequest(self.url))
        self.assertEqual(body, b'test')
        self.assertServerLogIs([
            ('GET', self.path, 404),
            ('GET', self.path, 200),
        ])

    def test_head(self):
        self.assertHTTPErrorCode(404, HeadRequest(self.url))
        self.http_server.create_file(self.filename, b'test')
        body = self.assertHttpSuccess(HeadRequest(self.url))
        self.assertEqual(body, b'')
        self.assertServerLogIs([
            ('HEAD', self.path, 404),
            ('HEAD', self.path, 200),
        ])

    def test_delete(self):
        # delete a non-existing file
        self.assertHTTPErrorCode(404, DeleteRequest(self.url))
        # delete an existing file
        self.http_server.create_file(self.filename, b'test')
        body = self.assertHttpSuccess(DeleteRequest(self.url))
        self.assertEqual(body, b'')
        self.assertFalse(self.http_server.has_file(self.filename))
        # attempt to put in read-only mode
        self.http_server.create_file(self.filename, b'test')
        self.http_server.readonly = True
        self.assertHTTPErrorCode(403, DeleteRequest(self.url, b'test'))
        self.assertServerLogIs([
            ('DELETE', self.path, 404),
            ('DELETE', self.path, 204),
            ('DELETE', self.path, 403),
        ])

    def test_put(self):
        # put a non-existing file
        body = self.assertHttpSuccess(PutRequest(self.url, b'test'))
        self.assertEqual(body, b'')
        self.assertEqual(self.http_server.get_file(self.filename), b'test')
        # put an existing file
        body = self.assertHttpSuccess(PutRequest(self.url, b'test2'))
        self.assertEqual(body, b'')
        self.assertEqual(self.http_server.get_file(self.filename), b'test2')
        # attempt to put in read-only mode
        self.http_server.readonly = True
        self.assertHTTPErrorCode(403, PutRequest(self.url, b'test'))
        self.assertServerLogIs([
            ('PUT', self.path, 201),
            ('PUT', self.path, 204),
            ('PUT', self.path, 403),
        ])
