import unittest
from eventapp.app import app

class TestEventSearch(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_search_event_by_name(self):
        response = self.app.get('/events?search=Music')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Music', response.data)

    def test_search_event_no_results(self):
        response = self.app.get('/events?search=NonExistentEvent')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Kh\xc3\xb4ng t\xc3\xacm th\xe1\xba\xa5y s\xe1\xbb\xb1 ki\xe1\xbb\x87n', response.data)

    def test_search_event_partial_match(self):
        response = self.app.get('/events?search=Fest')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Fest', response.data)

if __name__ == '__main__':
    unittest.main()
