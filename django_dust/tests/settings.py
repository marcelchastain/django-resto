import numbers

from django.utils import unittest

from ..settings import get_setting


class SettingsTestCase(unittest.TestCase):

    def test_get_existing_setting(self):
        self.assertIsInstance(get_setting('TIMEOUT'), numbers.Number)

    def test_get_non_existing_setting(self):
        self.assertRaises(KeyError, get_setting, 'TIME-OUT')
