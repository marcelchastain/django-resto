import BaseHTTPServer
import urllib2


class StopRequest(urllib2.Request):
    """Non-standard HTTP request, used to stop the test server."""
    def get_method(self):
        return 'STOP'


class TestHttpServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    """Request handler for the test HTTP server.

    Logging is disable to avoid spurious output during the tests.
    """

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
        self.send_response(code)
        self.send_header('Content-Length', 0)
        self.end_headers()

    def do_GET(self):
        return self.safe()

    def do_HEAD(self):
        return self.safe(include_content=False)

    def do_PUT(self):
        if self.server.readonly:
            self.send_error(403)
            return
        created = not self.server.has_file(self.filename)
        self.server.create_file(self.filename, self.content)
        self.no_content(201 if created else 204)

    def do_DELETE(self):
        if self.server.readonly:
            self.send_error(403)
            return
        try:
            self.server.delete_file(self.filename)
        except KeyError:
            self.send_error(404)
        else:
            self.no_content()

    def do_STOP(self):
        self.server.running = False
        self.no_content()

    def log_message(*args):
        pass    # disable logging


class TestHttpServer(BaseHTTPServer.HTTPServer):

    """Test HTTP server.

    This class provides a basic, in-memory implementation of GET, HEAD, PUT
    and DELETE, as well as a few methods to manage the pseudo-files.

    When readonly is True, PUT and DELETE requests are be forbidden.

    Once self.run() is called, the server will handle requests until it
    receives a request with a STOP method — see the StopRequest class.
    """

    def __init__(self, host='localhost', port=4080, readonly=False):
        self.files = {}
        self.readonly = readonly
        BaseHTTPServer.HTTPServer.__init__(self, (host, port),
                TestHttpServerRequestHandler)

    def has_file(self, name):
        return name in self.files

    def get_file(self, name):
        return self.files[name]

    def create_file(self, name, content):
        self.files[name] = content

    def delete_file(self, name):
        del self.files[name]

    def run(self):
        self.running = True
        while self.running:
            self.handle_request()
