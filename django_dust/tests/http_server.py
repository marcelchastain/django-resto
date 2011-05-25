import os
import os.path
import threading
import urllib2

from django.conf import settings
from django.utils import unittest

from ..http_server import GetRequest, HeadRequest, DeleteRequest, \
        PutRequest, StopRequest, TestHttpServer


class HttpServerTestCaseMixin(object):

    host = 'localhost'
    port = 4080
    readonly = False
    use_fs = False
    filename = 'test.txt'
    url = 'http://%s:%d/%s' % (host, port, filename)
    filepath = os.path.join(settings.MEDIA_ROOT, filename)

    def setUp(self):
        super(HttpServerTestCaseMixin, self).setUp()
        self.http_server = TestHttpServer(self.host, self.port,
            readonly=self.readonly, use_fs=self.use_fs)
        self.thread = threading.Thread(target=self.http_server.run)
        self.thread.start()

    def tearDown(self):
        super(HttpServerTestCaseMixin, self).tearDown()
        if self.thread.is_alive():
            urllib2.urlopen(StopRequest(self.url), timeout=0.1)
        self.thread.join()
        self.http_server.server_close()

    def assertHttpSuccess(self, *args):
        return urllib2.urlopen(*args).read()    # urllib2.URLError not raised.

    def assertHttpErrorCode(self, code, *args):
        with self.assertRaises(urllib2.URLError) as context:
            urllib2.urlopen(*args)
        self.assertEqual(context.exception.code, code, 'Expected HTTP %d, '
                'got HTTP %d' % (code, context.exception.code))


class HttpServerTestsMixin(object):

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
        if self.http_server.use_fs:
            self.assertFalse(os.path.exists(self.filepath))
        # attempt to put in read-only mode
        self.http_server.create_file(self.filename, 'test')
        self.http_server.readonly = True
        self.assertHttpErrorCode(500, DeleteRequest(self.url, 'test'))

    def test_put(self):
        # put a non-existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test'))
        self.assertEqual(body, '')
        self.assertEqual(self.http_server.get_file(self.filename), 'test')
        if self.http_server.use_fs:
            with open(self.filepath) as f:
                self.assertEqual(f.read(), 'test')
        # put an existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test2'))
        self.assertEqual(body, '')
        self.assertEqual(self.http_server.get_file(self.filename), 'test2')
        if self.http_server.use_fs:
            with open(self.filepath) as f:
                self.assertEqual(f.read(), 'test2')
        # attempt to put in read-only mode
        self.http_server.readonly = True
        self.assertHttpErrorCode(500, PutRequest(self.url, 'test'))

    def test_tear_down_works_even_if_server_is_stopped(self):
        self.assertHttpSuccess(StopRequest(self.url))


class HttpServerWithoutFsTestCase(HttpServerTestsMixin, HttpServerTestCaseMixin,
        unittest.TestCase):

    use_fs = False


class HttpServerWithFsTestCase(HttpServerTestsMixin, HttpServerTestCaseMixin,
        unittest.TestCase):

    use_fs = True