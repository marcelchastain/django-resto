import datetime
import os
import os.path
import shutil

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import unittest

from ..storage import DistributedStorage, HybridStorage
from .http_server import HttpServerTestCaseMixin


class StorageTestCaseMixin(object):

    def setUp(self):
        super(StorageTestCaseMixin, self).setUp()
        hosts = ['%s:%d' % (self.host, self.port)]
        self.storage = self.storage_class(hosts=hosts)

    def has_file(self, name):
        return self.http_server.has_file(name)

    def get_file(self, name):
        return self.http_server.get_file(name)

    def create_file(self, name, content):
        return self.http_server.create_file(name, content)

    def delete_file(self, name):
        return self.http_server.delete_file(name)

    # See http://docs.djangoproject.com/en/dev/ref/files/storage/
    # for the full storage API.
    # See http://docs.djangoproject.com/en/dev/howto/custom-file-storage/
    # for a list of which methods a custom storage class must implement.

    def test_accessed_time(self):
        self.create_file('test.txt', 'test')
        self.assertIsInstance(self.storage.accessed_time('test.txt'), datetime.datetime)
        self.delete_file('test.txt')
        self.assertRaises(EnvironmentError, self.storage.accessed_time, 'test.txt')

    def test_created_time(self):
        self.create_file('test.txt', 'test')
        self.assertIsInstance(self.storage.created_time('test.txt'), datetime.datetime)
        self.delete_file('test.txt')
        self.assertRaises(EnvironmentError, self.storage.created_time, 'test.txt')

    def test_delete(self):
        self.create_file('test.txt', 'test')
        self.assertTrue(self.has_file('test.txt'))
        self.storage.delete('test.txt')
        self.assertFalse(self.has_file('test.txt'))
        # deleting a file that doesn't exist doesn't raise an exception
        self.storage.delete('test.txt')
        self.assertFalse(self.has_file('test.txt'))

    def test_exists(self):
        self.assertFalse(self.storage.exists('test.txt'))
        self.create_file('test.txt', 'test')
        self.assertTrue(self.storage.exists('test.txt'))

    def test_get_available_name(self):
        self.assertEqual(self.storage.get_available_name('test.txt'), 'test.txt')
        self.create_file('test.txt', 'test')
        self.assertEqual(self.storage.get_available_name('test.txt'), 'test_1.txt')

    def test_get_valid_name(self):
        self.assertEqual(self.storage.get_valid_name('test.txt'), 'test.txt')

    def test_listdir(self):
        self.create_file('test/foo.txt', 'foo')
        self.create_file('test/bar.txt', 'bar')
        self.create_file('test/baz/quux.txt', 'quux')
        listing = self.storage.listdir('test')
        self.assertEqual(set(listing[0]), set(['baz']))
        self.assertEqual(set(listing[1]), set(['foo.txt', 'bar.txt']))

    def test_modified_time(self):
        self.create_file('test.txt', 'test')
        self.assertIsInstance(self.storage.modified_time('test.txt'), datetime.datetime)
        self.delete_file('test.txt')
        self.assertRaises(EnvironmentError, self.storage.modified_time, 'test.txt')

    def test_open(self):
        self.create_file('test.txt', 'test')
        with self.storage.open('test.txt') as f:
            self.assertEqual(f.read(), 'test')

    def test_path(self):
        self.create_file('test.txt', 'test')
        self.assertEqual(self.storage.path('test.txt'),
                         os.path.join(settings.MEDIA_ROOT, 'test.txt'))

    def test_save(self):
        filename = self.storage.save('test.txt', ContentFile('test'))
        self.assertEqual(filename, 'test.txt')
        self.assertEqual(self.get_file('test.txt'), 'test')
        filename = self.storage.save('test.txt', ContentFile('test2'))
        self.assertEqual(filename, 'test_1.txt')
        self.assertEqual(self.get_file('test_1.txt'), 'test2')

    def test_size(self):
        self.create_file('test.txt', 'test')
        self.assertEqual(self.storage.size('test.txt'), 4)

    def test_url(self):
        self.create_file('test.txt', 'test')
        self.assertEqual(self.storage.url('test.txt'),
                'http://media.example.com/test.txt')


class DistributedStorageTestCase(StorageTestCaseMixin,
        HttpServerTestCaseMixin, unittest.TestCase):

    storage_class = DistributedStorage

    # Disable tests of methods that are not implemented by DistributedStorage.

    def test_accessed_time(self):
        self.assertRaises(NotImplementedError, self.storage.accessed_time, 'test.txt')

    def test_created_time(self):
        self.assertRaises(NotImplementedError, self.storage.created_time, 'test.txt')

    def test_modified_time(self):
        self.assertRaises(NotImplementedError, self.storage.modified_time, 'test.txt')

    def test_listdir(self):
        self.assertRaises(NotImplementedError, self.storage.listdir, 'test')

    def test_path(self):
        self.assertRaises(NotImplementedError, self.storage.path, 'test.txt')


class HybridStorageTestCase(StorageTestCaseMixin,
        HttpServerTestCaseMixin, unittest.TestCase):

    storage_class = HybridStorage

    # Use the filesystem when creating or deleting a file on the test server.

    def create_file(self, name, content):
        super(HybridStorageTestCase, self).create_file(name, content)
        filename = os.path.join(settings.MEDIA_ROOT, name)
        if not os.path.isdir(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'wb') as f:
            f.write(content)

    def delete_file(self, name):
        super(HybridStorageTestCase, self).delete_file(name)
        filename = os.path.join(settings.MEDIA_ROOT, name)
        os.unlink(filename)

    def setUp(self):
        super(HybridStorageTestCase, self).setUp()
        os.makedirs(settings.MEDIA_ROOT)

    def tearDown(self):
        super(HybridStorageTestCase, self).tearDown()
        shutil.rmtree(settings.MEDIA_ROOT)
