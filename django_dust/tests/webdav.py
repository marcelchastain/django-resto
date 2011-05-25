import BaseHTTPServer
import os
import os.path
import shutil
import threading
import urllib2

from django.conf import settings
from django.utils import unittest


class HeadRequest(urllib2.Request):
    def get_method(self):
        return 'HEAD'


class DeleteRequest(urllib2.Request):
    def get_method(self):
        return 'DELETE'


class PutRequest(urllib2.Request):
    def get_method(self):
        return 'PUT'


class StopRequest(urllib2.Request):
    def get_method(self):
        return 'STOP'


class TestWebdavRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    @property
    def filename(self):
        return self.path.lstrip('/')

    @property
    def content(self):
        return self.rfile.read(int(self.headers['Content-Length']))

    def safe(self, include_content=True):
        try:
            content = self.server.get_file(self.filename)
        except KeyError:
            self.send_error(404)
        else:
            self.send_response(200)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            if include_content:
                self.wfile.write(content)

    def no_content(self, code=204):
        self.send_response(204)
        self.send_header('Content-Length', 0)
        self.end_headers()

    def do_GET(self):
        return self.safe()

    def do_HEAD(self):
        return self.safe(include_content=False)

    def do_DELETE(self):
        if self.server.readonly:
            self.send_error(500)
            return
        try:
            self.server.delete_file(self.filename)
        except KeyError:
            self.send_error(404)
        else:
            self.no_content()

    def do_PUT(self):
        if self.server.readonly:
            self.send_error(500)
            return
        created = not self.server.has_file(self.filename)
        self.server.create_file(self.filename, self.content)
        self.no_content(201 if created else 204)

    def do_STOP(self):
        self.server.running = False
        self.no_content()

    def log_message(*args):
        pass    # disable logging


class TestWebdavServer(BaseHTTPServer.HTTPServer):

    def __init__(self, host='localhost', port=4080,
            readonly=False, use_fs=False):
        self.files = {}
        self.readonly = readonly
        self.use_fs = use_fs
        BaseHTTPServer.HTTPServer.__init__(self, (host, port),
                TestWebdavRequestHandler)

    def has_file(self, name):
        return name in self.files

    def get_file(self, name):
        return self.files[name]

    def create_file(self, name, content):
        self.files[name] = content
        if self.use_fs:
            filename = os.path.join(settings.MEDIA_ROOT, name)
            if not os.path.isdir(os.path.dirname(filename)):
                os.makedirs(os.path.dirname(filename))
            with open(filename, 'wb') as f:
                f.write(content)

    def delete_file(self, name):
        del self.files[name]
        if self.use_fs:
            filename = os.path.join(settings.MEDIA_ROOT, name)
            os.unlink(filename)

    def run(self):
        self.running = True
        while self.running:
            self.handle_request()
        if self.use_fs and os.path.isdir(settings.MEDIA_ROOT):
            shutil.rmtree(settings.MEDIA_ROOT)


class WebdavTestCaseMixin(object):

    host = 'localhost'
    port = 4080
    readonly = False
    use_fs = False
    filename = 'test.txt'
    url = 'http://%s:%d/%s' % (host, port, filename)
    filepath = os.path.join(settings.MEDIA_ROOT, filename)

    def setUp(self):
        super(WebdavTestCaseMixin, self).setUp()
        self.webdav = TestWebdavServer(self.host, self.port,
            readonly=self.readonly, use_fs=self.use_fs)
        self.thread = threading.Thread(target=self.webdav.run)
        self.thread.start()

    def tearDown(self):
        super(WebdavTestCaseMixin, self).tearDown()
        if self.thread.is_alive():
            urllib2.urlopen(StopRequest(self.url), timeout=0.1)
        self.thread.join()
        self.webdav.server_close()

    def assertHttpSuccess(self, *args):
        return urllib2.urlopen(*args).read()    # urllib2.URLError not raised.

    def assertHttpErrorCode(self, code, *args):
        with self.assertRaises(urllib2.URLError) as context:
            urllib2.urlopen(*args)
        self.assertEqual(context.exception.code, code, 'Expected HTTP %d, '
                'got HTTP %d' % (code, context.exception.code))


class WebdavServerTestsMixin(object):

    def test_get(self):
        self.assertHttpErrorCode(404, urllib2.Request(self.url))
        self.webdav.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(urllib2.Request(self.url))
        self.assertEqual(body, 'test')

    def test_head(self):
        self.assertHttpErrorCode(404, HeadRequest(self.url))
        self.webdav.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(HeadRequest(self.url))
        self.assertEqual(body, '')

    def test_delete(self):
        # delete a non-existing file
        self.assertHttpErrorCode(404, DeleteRequest(self.url))
        # delete an existing file
        self.webdav.create_file(self.filename, 'test')
        body = self.assertHttpSuccess(DeleteRequest(self.url))
        self.assertEqual(body, '')
        self.assertFalse(self.webdav.has_file(self.filename))
        if self.webdav.use_fs:
            self.assertFalse(os.path.exists(self.filepath))
        # attempt to put in read-only mode
        self.webdav.create_file(self.filename, 'test')
        self.webdav.readonly = True
        self.assertHttpErrorCode(500, DeleteRequest(self.url, 'test'))

    def test_put(self):
        # put a non-existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test'))
        self.assertEqual(body, '')
        self.assertEqual(self.webdav.get_file(self.filename), 'test')
        if self.webdav.use_fs:
            with open(self.filepath) as f:
                self.assertEqual(f.read(), 'test')
        # put an existing file
        body = self.assertHttpSuccess(PutRequest(self.url, 'test2'))
        self.assertEqual(body, '')
        self.assertEqual(self.webdav.get_file(self.filename), 'test2')
        if self.webdav.use_fs:
            with open(self.filepath) as f:
                self.assertEqual(f.read(), 'test2')
        # attempt to put in read-only mode
        self.webdav.readonly = True
        self.assertHttpErrorCode(500, PutRequest(self.url, 'test'))

    def test_tear_down_works_even_if_server_is_stopped(self):
        self.assertHttpSuccess(StopRequest(self.url))


class WebdavWithoutFsTestCase(WebdavServerTestsMixin, WebdavTestCaseMixin,
        unittest.TestCase):

    use_fs = False


class WebdavWithFsTestCase(WebdavServerTestsMixin, WebdavTestCaseMixin,
        unittest.TestCase):

    use_fs = True
