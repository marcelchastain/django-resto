import os
import os.path
import shutil

from django.conf import settings
from django.utils import unittest

from ..storage import DistributedStorage
from .webdav import WebdavTestCaseMixin


class StorageAPIMixin(object):

    def create_test_file(self, name='test.txt', content='test'):
        raise NotImplementedError()

    def test_delete(self):
        self.create_test_file()
        self.storage.delete('test.txt')
        self.assertNotIn('/test.txt', self.webdav.files)
        # deleting a file that doesn't exist doesn't raise an exception
        self.storage.delete('test.txt')

    def test_exists(self):
        self.assertFalse(self.storage.exists('test.txt'))
        self.create_test_file()
        self.assertTrue(self.storage.exists('test.txt'))

    def test_listdir(self):
        self.create_test_file('test/foo.txt', 'foo')
        self.create_test_file('test/bar.txt', 'bar')
        self.create_test_file('test/baz/quux.txt', 'quux')
        listing = self.storage.listdir('test')
        self.assertEqual(set(listing[0]), set([u'baz']))
        self.assertEqual(set(listing[1]), set([u'foo.txt', u'bar.txt']))

    def test_size(self):
        self.create_test_file()
        self.assertEqual(self.storage.size('test.txt'), 4)

    def test_url(self):
        self.create_test_file()
        self.assertEqual(self.storage.url('test.txt'),
                'http://media.example.com/test.txt')


class StorageAPIWithoutLocalStorageTestCase(
        StorageAPIMixin, WebdavTestCaseMixin, unittest.TestCase):

    def setUp(self):
        super(StorageAPIWithoutLocalStorageTestCase, self).setUp()
        hosts = ['%s:%d' % (self.host, self.port)]
        self.storage = DistributedStorage(hosts=hosts, use_local=False)

    def create_test_file(self, name='test.txt', content='test'):
        self.webdav.files['/' + name] = content

    def test_listdir(self):
        pass            # listdir is not implemented without local storage


class StorageAPIWithLocalStorageTestCase(
        StorageAPIMixin, WebdavTestCaseMixin, unittest.TestCase):

    def setUp(self):
        super(StorageAPIWithLocalStorageTestCase, self).setUp()
        hosts = ['%s:%d' % (self.host, self.port)]
        self.storage = DistributedStorage(hosts=hosts, use_local=True)
        os.makedirs(settings.MEDIA_ROOT)

    def tearDown(self):
        super(StorageAPIWithLocalStorageTestCase, self).tearDown()
        shutil.rmtree(settings.MEDIA_ROOT)

    def create_test_file(self, name='test.txt', content='test'):
        self.webdav.files['/' + name] = content
        filename = os.path.join(settings.MEDIA_ROOT, name)
        if not os.path.isdir(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'wb') as f:
            f.write(content)
