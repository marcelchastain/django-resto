import BaseHTTPServer
import os
import os.path
import shutil
import urllib2

from django.conf import settings


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
