import BaseHTTPServer
import threading
import urllib2

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

    def safe(self, include_content=True):
        try:
            content = self.server.files[self.path]
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
        try:
            del self.server.files[self.path]
        except KeyError:
            self.send_error(404)
        else:
            self.no_content()

    def do_PUT(self):
        created = self.path not in self.server.files
        content_length = int(self.headers['Content-Length'])
        self.server.files[self.path] = self.rfile.read(content_length)
        self.no_content(201 if created else 204)

    def do_STOP(self):
        self.server.running = False
        self.no_content()

    def log_message(*args):
        pass    # disable logging


class TestWebdavServer(BaseHTTPServer.HTTPServer):

    def __init__(self, host='localhost', port=4080):
        self.files = {}
        BaseHTTPServer.HTTPServer.__init__(self, (host, port), TestWebdavRequestHandler)

    def run(self):
        self.running = True
        while True:
            self.handle_request()
            if not self.running:
                break


class WebdavTestCaseMixin(object):

    host = 'localhost'
    port = 4080
    url = 'http://%s:%d/' % (host, port)

    def setUp(self):
        self.webdav = TestWebdavServer(self.host, self.port)
        self.thread = threading.Thread(target=self.webdav.run)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
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


class WebdavServerTestCase(WebdavTestCaseMixin, unittest.TestCase):

    def test_get(self):
        self.assertHttpErrorCode(404, urllib2.Request(self.url))
        self.webdav.files['/'] = 'test'
        body = self.assertHttpSuccess(urllib2.Request(self.url))
        self.assertEqual(body, 'test')

    def test_head(self):
        self.assertHttpErrorCode(404, HeadRequest(self.url))
        self.webdav.files['/'] = 'test'
        body = self.assertHttpSuccess(HeadRequest(self.url))
        self.assertEqual(body, '')

    def test_delete(self):
        self.assertHttpErrorCode(404, DeleteRequest(self.url))
        self.webdav.files['/'] = 'test'
        body = self.assertHttpSuccess(DeleteRequest(self.url))
        self.assertEqual(body, '')
        self.assertNotIn('/', self.webdav.files)

    def test_put(self):
        body = self.assertHttpSuccess(PutRequest(self.url, 'test'))
        self.assertEqual(body, '')
        self.assertEqual(self.webdav.files['/'], 'test')
        body = self.assertHttpSuccess(PutRequest(self.url, 'test2'))
        self.assertEqual(body, '')
        self.assertEqual(self.webdav.files['/'], 'test2')
