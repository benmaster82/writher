import os
import tempfile
import unittest
from unittest.mock import patch

NOTE_CONTENT = "Learn for software engineering"
NOTE_TITLE = "Study"
NOTE_KEYWORD = "software"
APPOINTMENT_TITLE = "Short test"
APPOINTMENT_DT = "2026-06-01T10:15"
APPOINTMENT_KEYWORD = "short"
REMINDER_MESSAGE = "Learn for test"
REMINDER_DT = "2026-05-26T18:00"
REMINDER_KEYWORD = "learn"


class TestDeleteDB(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._db = os.path.join(self._tmp, 'test.db')
        self._patch = patch('database.DB_PATH', self._db)
        self._patch.start()
        import database
        database.init()
        self.db = database

    def tearDown(self):
        self._patch.stop()

    def test_find_note_by_keyword(self):
        self.db.save_note(NOTE_CONTENT, title=NOTE_TITLE)
        result = self.db.find_note_by_keyword(NOTE_KEYWORD)
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], NOTE_TITLE)
        self.assertEqual(result['content'], NOTE_CONTENT)
    
    def test_find_appointment_by_keyword(self):
        self.db.create_appointment(APPOINTMENT_TITLE, APPOINTMENT_DT)
        result = self.db.find_appointment_by_keyword(APPOINTMENT_KEYWORD)
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], APPOINTMENT_TITLE)
        self.assertEqual(result['dt'], APPOINTMENT_DT)
    
    def test_find_reminder_by_keyword(self):
        self.db.set_reminder(REMINDER_MESSAGE, REMINDER_DT)
        result = self.db.find_reminder_by_keyword(REMINDER_KEYWORD)
        self.assertIsNotNone(result)
        self.assertEqual(result['message'], REMINDER_MESSAGE)
        self.assertEqual(result['remind_at'], REMINDER_DT)


class TestDeleteDispatch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._db  = os.path.join(self._tmp, "test.db")
        self._patch   = patch("database.DB_PATH", self._db)
        self._patch.start()
        import database
        database.init()
        self.db = database
        from assistant import _dispatch
        self._dispatch = _dispatch

    def tearDown(self):
        self._patch.stop()

    def test_delete_note_returns_confirmation(self):
        self.db.save_note(NOTE_CONTENT, title=NOTE_TITLE)
        result = self._dispatch({"function": "delete_note",
                                 "arguments": {"keyword": NOTE_KEYWORD}})
        self.assertTrue(result.startswith("__confirm_delete__:note:"))

    def test_delete_appointment_returns_confirmation(self):
        self.db.create_appointment(APPOINTMENT_TITLE, APPOINTMENT_DT)
        result = self._dispatch({"function": "delete_appointment",
                                 "arguments": {"keyword": APPOINTMENT_KEYWORD}})
        self.assertTrue(result.startswith("__confirm_delete__:appointment:"))

    def test_delete_reminder_returns_confirmation(self):
        self.db.set_reminder(REMINDER_MESSAGE, REMINDER_DT)
        result = self._dispatch({"function": "delete_reminder",
                                 "arguments": {"keyword": REMINDER_KEYWORD}})
        self.assertTrue(result.startswith("__confirm_delete__:reminder:"))


if __name__ == '__main__':
    unittest.main()