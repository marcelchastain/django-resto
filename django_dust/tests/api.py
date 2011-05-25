import os.path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import unittest

from ..storage import DistributedStorage
from .webdav import WebdavTestCaseMixin


class StorageTestCaseMixin(object):

    def setUp(self):
        super(StorageTestCaseMixin, self).setUp()
        hosts = ['%s:%d' % (self.host, self.port)]
        self.storage = DistributedStorage(hosts=hosts, use_local=self.use_fs)

class StorageAPIMixin(object):

    # See http://docs.djangoproject.com/en/dev/ref/files/storage/
    # for the full storage API.
    # See http://docs.djangoproject.com/en/dev/howto/custom-file-storage/
    # for a list of which methods a custom storage class must implement.

    def test_accessed_time(self):
        self.assertRaises(NotImplementedError,
                self.storage.accessed_time, 'test.txt')

    def test_created_time(self):
        self.assertRaises(NotImplementedError,
                self.storage.created_time, 'test.txt')

    def test_delete(self):
        self.webdav.create_file('test.txt', 'test')
        self.assertTrue(self.webdav.has_file('test.txt'))
        self.storage.delete('test.txt')
        self.assertFalse(self.webdav.has_file('test.txt'))
        # deleting a file that doesn't exist doesn't raise an exception
        self.storage.delete('test.txt')
        self.assertFalse(self.webdav.has_file('test.txt'))

    def test_exists(self):
        self.assertFalse(self.storage.exists('test.txt'))
        self.webdav.create_file('test.txt', 'test')
        self.assertTrue(self.storage.exists('test.txt'))

    def test_get_available_name(self):
        self.assertEqual(self.storage.get_available_name('test.txt'), 'test.txt')
        self.webdav.create_file('test.txt', 'test')
        self.assertEqual(self.storage.get_available_name('test.txt'), 'test_.txt')

    def test_get_valid_name(self):
        self.assertEqual(self.storage.get_valid_name('test.txt'), 'test.txt')

    def test_listdir(self):
        self.webdav.create_file('test/foo.txt', 'foo')
        self.webdav.create_file('test/bar.txt', 'bar')
        self.webdav.create_file('test/baz/quux.txt', 'quux')
        listing = self.storage.listdir('test')
        self.assertEqual(set(listing[0]), set(['baz']))
        self.assertEqual(set(listing[1]), set(['foo.txt', 'bar.txt']))

    def test_modified_time(self):
        self.assertRaises(NotImplementedError,
                self.storage.modified_time, 'test.txt')

    def test_open(self):
        self.webdav.create_file('test.txt', 'test')
        with self.storage.open('test.txt') as f:
            self.assertEqual(f.read(), 'test')

    def test_path(self):
        self.webdav.create_file('test.txt', 'test')
        self.assertEqual(self.storage.path('test.txt'),
                         os.path.join(settings.MEDIA_ROOT, 'test.txt'))

    def test_save(self):
        filename = self.storage.save('test.txt', ContentFile('test'))
        self.assertEqual(filename, 'test.txt')
        self.assertEqual(self.webdav.get_file('test.txt'), 'test')
        filename = self.storage.save('test.txt', ContentFile('test2'))
        self.assertEqual(filename, 'test_.txt')
        self.assertEqual(self.webdav.get_file('test_.txt'), 'test2')

    def test_size(self):
        self.webdav.create_file('test.txt', 'test')
        self.assertEqual(self.storage.size('test.txt'), 4)

    def test_url(self):
        self.webdav.create_file('test.txt', 'test')
        self.assertEqual(self.storage.url('test.txt'),
                'http://media.example.com/test.txt')


class StorageAPIWithoutLocalStorageTestCase(StorageAPIMixin,
        StorageTestCaseMixin, WebdavTestCaseMixin, unittest.TestCase):

    def test_listdir(self):
        self.assertRaises(NotImplementedError, self.storage.listdir, 'test')

    def test_path(self):
        self.assertRaises(NotImplementedError, self.storage.path, 'test.txt')


class StorageAPIWithLocalStorageTestCase(StorageAPIMixin,
        StorageTestCaseMixin, WebdavTestCaseMixin, unittest.TestCase):

    use_fs = True
