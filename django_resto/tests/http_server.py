import os.path
import threading
import urllib2

from django.conf import settings
from django.utils import unittest

from ..http_server import StopRequest, TestHttpServer
from ..storage import GetRequest, HeadRequest, DeleteRequest, PutRequest


class HttpServerTestCaseMixin(object):

    host = 'localhost'
    port = 4080
    filename = 'test.txt'
    url = 'http://%s:%d/%s' % (host, port, filename)
    filepath = os.path.join(settings.MEDIA_ROOT, filename)

    def setUp(self):
        super(HttpServerTestCaseMixin, self).setUp()
        self.http_server = TestHttpServer(self.host, self.port)
        self.thread = threading.Thread(target=self.http_server.run)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        super(HttpServerTestCaseMixin, self).tearDown()
        try:
            urllib2.urlopen(StopRequest(self.url), timeout=0.1)
        except urllib2.URLError:
            pass
        self.http_server.server_close()

    def assertHttpSuccess(self, *args):
        return urllib2.urlopen(*args).read()    # urllib2.URLError not raised.

    def assertHttpErrorCode(self, code, *args):
        with self.assertRaises(urllib2.URLError) as context:
            urllib2.urlopen(*args)
        self.assertEqual(context.exception.code, code, 'Expected HTTP %d, '
                'got HTTP %d' % (code, context.exception.code))


class ExtraHttpServerTestCaseMixin(object):

    def setUp(self):
        super(ExtraHttpServerTestCaseMixin, self).setUp()

        self.alt_http_server = TestHttpServer(self.host, self.port + 1)
        self.alt_thread = threading.Thread(target=self.alt_http_server.run)
        self.alt_thread.daemon = True
        self.alt_thread.start()
        self.alt_url = 'http://%s:%d/' % (self.host, self.port + 1)

    def tearDown(self):
        try:
            urllib2.urlopen(StopRequest(self.alt_url), timeout=0.1)
        except urllib2.URLError:
            pass
        self.alt_thread.join()
        self.alt_http_server.server_close()
        super(ExtraHttpServerTestCaseMixin, self).tearDown()


class HttpServerTestCase(HttpServerTestCaseMixin, unittest.TestCase):

    def test_get(self):
        self.assertHttpErrorCode(404, GetRequest(self.url))
        self.http_server.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(GetRequest(self.url))
        self.assertEqual(body, 'test')

    def test_head(self):
        self.assertHttpErrorCode(404, HeadRequest(self.url))
        self.http_server.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(HeadRequest(self.url))
        self.assertEqual(body, '')

    def test_delete(self):
        # delete a non-existing file
        self.assertHttpErrorCode(404, DeleteRequest(self.url))
        # delete an existing file
        self.http_server.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(DeleteRequest(self.url))
        self.assertEqual(body, '')
        self.assertFalse(self.http_server.has_file(self.filename))
        # attempt to put in read-only mode
        self.http_server.create_file(self.filename, 'test')
        self.http_server.readonly = True
        self.assertHttpErrorCode(403, DeleteRequest(self.url, 'test'))

    def test_put(self):
        # put a non-existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test'))
        self.assertEqual(body, '')
        self.assertEqual(self.http_server.get_file(self.filename), 'test')
        # put an existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test2'))
        self.assertEqual(body, '')
        self.assertEqual(self.http_server.get_file(self.filename), 'test2')
        # attempt to put in read-only mode
        self.http_server.readonly = True
        self.assertHttpErrorCode(403, PutRequest(self.url, 'test'))


class HttpServerShutDownTestCase(ExtraHttpServerTestCaseMixin,
        HttpServerTestCaseMixin, unittest.TestCase):

    def test_tear_down_works_even_if_server_is_stopped(self):
        self.assertHttpSuccess(StopRequest(self.url))

    def test_tear_down_works_even_if_alt_server_is_stopped(self):
        self.assertHttpSuccess(StopRequest(self.alt_url))
