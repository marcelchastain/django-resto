# README

## Introduction

`django_dust` (Distributed Upload STorage) provides file storage backends that
can store files coming into a Django site on several servers simultaneously,
using HTTP. `HybridStorage` will store the files locally on the filesystem and
remotely, while `DistributedStorage` will only store them remotely.

This works for files uploaded by users through the admin or through custom
Django forms, and also for files created by the application code, provided it
uses the standard [storage API][1].

`django_dust` is useful for sites deployed in a multi-server environment, in
order to accept uploaded files and have them available on all media servers
immediately for subsequent web requests that could be routed to any machine.


## How to use `django_dust`

### Recommended setup

In an infrastructure for a Django website, each server has one (or several) of
the following roles:

- Frontend servers handle directly HTTP requests for media and static files,
  and forward other requests to the **application servers**. For
  `django_dust`, the interesting part is that they are serving media files,
  so we call them **media servers**.
- Application servers run the Django application. This is where `django_dust`
  is installed.
- Database servers support the database.

If you have several application servers, you should store a **master copy** of
your media files on a NAS or a SAN attached to all your application servers.
If you have a single application server, you can also store the master copy on
the application server itself.

In both cases, use `HybridStorage` to replicate uploaded files on all the
media servers. Serving the media files from the local filesystem is more
efficient than serving them from a NAS or a SAN. This is the main advantage of
`django_dust`.

### A little bit of theoretical background

Django's built-in `FileSystemStorage` goes to great lengths to avoid race
conditions and ensure data integrity.

It is difficult for `django_dust` to provide the same guarantees, because of
the [CAP theorem][2]. Instead, its storage backends can be configured to
adjust the trade-off between the following properties:

- **Consistency**: this is a intrisic weakness of `django_dust`, because it
  uses plain HTTP, which doesn't provide transaction support, all the more
  with several hosts. However, it targets _eventual consistency_.
- **Availability**: `django_dust` generally improves the system's availability
  by replicating the data on several servers. Also, it parallelizes storage
  actions to minimize response time.
- **Partition tolerance**: `django_dust` is designed to cope with hardware or
  network failure. You can choose to maximize availability or consistency when
  such problems occur.

### Keeping media directories synchronized

You can configure the behavior of `django_dust` when a media server is
unavailable:

- If `DUST_FATAL_EXCEPTIONS` is `True`, which is the default value,
  `django_dust` will raise an exception whenever an operation doesn't succeed
  on all media servers. From the user's point of view, this usually results in
  an HTTP 500 error, unless you have some advanced error handling. This
  ensures that a failure won't go unnoticed.
- If `DUST_FATAL_EXCEPTIONS` is `False`, `django_dust` will log a message at
  level `ERROR` for each failed upload. This is useful if you want high
  availability: if one media server is down, you can still upload and delete
  files.

In either case, since each operation is run in parallel on all the servers, it
may succeed on some and fail on others. This results in an inconsistent state
on the media servers. When you bring a broken server back online, you must
re-synchronize the contents of its `MEDIA_ROOT` from the master copy, for
instance with `rsync`. You can also set up a cron if you get random failures
during load peaks. This provides eventual consistency.

Obviously, if you bring an additional media server online, you must
synchronize the content of its `MEDIA_ROOT` from the master copy.

_`django_dust` used to keep a queue of failed operations to repeat them
afterwards. This is inherently prone to data loss, because the order of `PUT`
and `DELETE` operations matters, and retrying failed operations later breaks
the order. So, use `rsync` instead, it's fast enough._

### Low concurrency situations

You may have several servers for high availability or read performance, but
still expect a low concurrency on write operations. This is a common pattern
for editorial websites. In such circumstances, you can decide not to store a
master copy of your media files on the application server. This behavior is
implemented by `DistributedStorage`.

Be aware of the consequences:

- It is very highly discouraged to set `DUST_FATAL_EXCEPTIONS` to `False`,
  because you could lose uploaded files entirely without an exception. As a
  consequence, you can't have high availability for write operations.
- Race conditions become possible: if two people upload different files with
  the same name at the same time, you may randomly end up with one file or the
  other on each media server.
- Checking if a file exists becomes more expensive, because it requires an
  HTTP request.


## Setup

### Installation guide

1.  Download and install the package from PyPI:

        $ pip install django_dust

2.  Add django_dust to `INSTALLED_APPS`:

        INSTALLED_APPS += 'django_dust',

3.  Set a default file backend, if you want all your models to use it:

        DEFAULT_FILE_STORAGE = 'django_dust.storage.HybridStorage'

    This is optional. You can also enable a backend only for selected fields
    in your models.

4.  Define the list of your media servers:

        DUST_MEDIA_HOSTS = ['media-%02d:8080' % i for i in range(12)]

    OK, maybe you don't have 12 servers just yet.

5.  Make sure you have configured `MEDIA_ROOT` and `MEDIA_URL`.

6.  Set up your media servers to enable file uploads.

### Backends

`django_dust` defines two backends in `django_dust.storage`.

#### `HybridStorage`

With this backend, `django_dust` will run all file storage operations on
`MEDIA_ROOT` first, then replicate them to the media servers.

#### `DistributedStorage`

With this backend, `django_dust` will only store the files on the media
servers. See "Low concurrency situations" above.

### Settings

#### `DUST_FATAL_EXCEPTIONS`

Default: `True`

Whether to throw an exception when an operation fails on a media server.

Failed operations are always logged.

#### `DUST_MEDIA_HOSTS`

Default: `()`

List of host names for the media servers.

The URL used to upload or delete a given media file is built using
`MEDIA_URL`. It is the same URL used by the end user to download the file,
except that the host name changes. It isn't possible to use HTTPS.

#### `DUST_TIMEOUT`

Default: `2`

Timeout in seconds for HTTP operations.

This controls the maximum amount of time an upload operation can take. Note
that all uploads run in parallel.


## Configuring the media servers

The backend uses HTTP to transfer files to media servers. The HTTP server must
support the `PUT` and `DELETE` methods according to RFC 2616.

In practice, these methods are often provided by an external module that
implements WebDAV (RFC 2518). Unfortunately, WebDAV adds the concept of
"collections" and changes the specification of the `PUT` methods, making it
necessary to create a collection with `MKCOL` before creating a resource with
`PUT`. Currently, `django_dust` requires a server that just implements
HTTP/1.1 (RFC 2616).

**It's critical to enable file uploads only from trusted IPs.** Otherwise,
anyone could write or delete files on your media servers.

Here is an example of lighttpd config:

    server.modules += (
      "mod_webdav",
    )

    $HTTP["remoteip"] ~= "^192\.168\.0\.[0-9]+$" {
      "webdav.activate = "enable"
    }

Here is an example of nginx config, assuming the server was compiled
`--with-http_dav_module`:

    server {
        listen 192.168.0.10;
        location / {
            root /var/www/media;
            dav_methods PUT DELETE;
            create_full_put_path on;
            dav_access user:rw group:r all:r;
            allow 192.168.0.1/24;
            deny all;
        }
    }


[1]: http://docs.djangoproject.com/en/dev/ref/files/storage/
[2]: http://en.wikipedia.org/wiki/CAP_theorem
