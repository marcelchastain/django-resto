class BaseRetryStorage(object):
    """Pluggable interface for retry queue storage."""

    fields = ['operation', 'target_host', 'source_host', 'filename']

    def count(self):
        """Return total retry count."""
        raise NotImplementedError

    def all(self):
        """Return all retries in queue."""
        raise NotImplementedError

    def create(self, **kwargs):
        """Create a new retry object in queue."""
        raise NotImplementedError

    def delete(self, retry):
        """Delete the given retry object from queue."""
        raise NotImplementedError

    def filter_by_filename(self, filename):
        """Return retry objects for a given file name."""
        raise NotImplementedError
