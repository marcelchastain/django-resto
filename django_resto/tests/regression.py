# coding: utf-8

from django.utils import unittest

from .storage import StorageUtilitiesMixin, UseDistributedStorageMixin


class RegressionTestCase(
    StorageUtilitiesMixin, UseDistributedStorageMixin, unittest.TestCase):

    def test_non_ascii_file_name(self):
        self.create_file(u'café.txt', 'caffeine')
        self.assertTrue(self.storage.exists(u'café.txt'))
        self.delete_file(u'café.txt')
        self.assertFalse(self.storage.exists(u'café.txt'))
