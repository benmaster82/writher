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
        # print(f"Using temporary database at {self._db}")

    def tearDown(self):
        self._patch.stop()

    def test_find_note_by_keyword(self):
        self.db.save_note("Learn for software engineering", title="Study")
        result = self.db.find_note_by_keyword("Study")
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Study")
        self.assertEqual(result['content'], "Learn for software engineering")
    
    def test_find_appointment_by_keyword(self):
        self.db.create_appointment("Test am Rechner", "2026-06-01T10:15")
        result = self.db.find_appointment_by_keyword("Test")
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Test am Rechner")
        self.assertEqual(result['dt'], "2026-06-01T10:15")
    
    def test_find_reminder_by_keyword(self):
        self.db.set_reminder("Learn for test", "2026-05-26T18:00")
        result = self.db.find_reminder_by_keyword("Learn")
        self.assertIsNotNone(result)
        self.assertEqual(result['message'], "Learn for test")
        self.assertEqual(result['remind_at'], "2026-05-26T18:00")


if __name__ == '__main__':
    unittest.main()