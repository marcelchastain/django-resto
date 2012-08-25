# coding: utf-8
from __future__ import unicode_literals

from django.utils import unittest

from .storage import StorageUtilitiesMixin, UseDistributedStorageMixin


class RegressionTestCase(
    StorageUtilitiesMixin, UseDistributedStorageMixin, unittest.TestCase):

    def test_non_ascii_file_name(self):
        self.create_file('café.txt', b'caffeine')
        self.assertTrue(self.storage.exists('café.txt'))
        self.delete_file('café.txt')
        self.assertFalse(self.storage.exists('café.txt'))
