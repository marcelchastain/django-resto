from __future__ import unicode_literals

import socket
try:                                                        # cover: disable
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import unquote
    from urllib.request import URLError, urlopen
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from urllib import unquote
    from urllib2 import URLError, urlopen


class TestHttpServerRequestHandler(BaseHTTPRequestHandler):

    """Request handler for the test HTTP server.

    Console logging is disabled to avoid spurious output during the tests.
    """

    @property
    def filename(self):
        if isinstance(self.path, bytes):                # Python 2
            return unquote(self.path.lstrip(b'/')).decode('utf-8')
        else:                                           # cover: disable
            return unquote(self.path.lstrip('/'))

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

    def log_request(self, code=None, size=None):
        code = self.server.override_code or code
        self.server.log.append((self.command, self.path, code))

    def log_message(self, *args):
        pass    # disable logging

    def send_response(self, code, message=None):
        BaseHTTPRequestHandler.send_response(self,
            self.server.override_code or code, message)


class TestHttpServer(HTTPServer):

    """Test HTTP server.

    This class provides a basic, in-memory implementation of GET, HEAD, PUT
    and DELETE, as well as a few methods to manage the pseudo-files.

    self.log keeps a record of (method, path, response code) for each query.

    When self.override_code isn't None, this HTTP status code is returned in
    every response.

    When self.readonly is True, PUT and DELETE requests are forbidden.

    self.override_code and self.readonly are used to test invalid behaviors.
    """

    def __init__(self, host='localhost', port=4080):
        self.files = {}
        self.log = []
        self.override_code = None
        self.readonly = False
        self.running = True
        HTTPServer.__init__(self, (host, port), TestHttpServerRequestHandler)

    def has_file(self, name):
        """Test if a file exists on the server."""
        return name in self.files

    def get_file(self, name):
        """Obtain the contents of a file on the server."""
        return self.files[name]

    def create_file(self, name, content):
        """Create a file on the server."""
        self.files[name] = content

    def delete_file(self, name):
        """Delete a file on the server."""
        del self.files[name]

    def run(self):
        """Start the server.

        It will handle requests until it receives a request with a STOP method.
        """
        while self.running:
            self.handle_request()

    def stop(self, timeout=0.1):
        """Stop the server."""
        if self.running:
            self.running = False
            # Make a random query to unblock the main loop.
            try:
                urlopen('http://%s:%d/' % self.server_address, timeout=timeout)
            except (URLError, socket.timeout):
                pass
        else:                                               # cover: disable
            print("Warning: stop() called with server wasn't running!")
