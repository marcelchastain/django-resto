from django.core import management
from django.test import TestCase


class RetryQueueTestCase(TestCase):

    def test_empty_queue(self):
        management.call_command('process_failed_media')
