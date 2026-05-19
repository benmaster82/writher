import os
import tempfile
import unittest
from unittest.mock import patch

class TestDeleteDB(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._db = os.path.join(self._tmp, 'test.db')
        self._patch = patch('database.DB_PATH', self._db)
        self._patch.start()
        import database
        database.init()
        self.db = database
        print(f"Using temporary database at {self._db}")

    def tearDown(self):
        self._patch.stop()

    def test_find_note_by_keyword_found(self):
        pass


if __name__ == '__main__':
    unittest.main()