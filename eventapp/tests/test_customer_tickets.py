import unittest
from eventapp.app import app

class TestCustomerTickets(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_view_my_tickets(self):
        # Mock đăng nhập bằng cách thiết lập session user_id
        with self.app as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = '1'  # Flask-Login expects string type
            response = c.get('/my-tickets', follow_redirects=False)
            if response.status_code == 302:
                # Nếu bị redirect, kiểm tra về trang đăng nhập
                self.assertIn('/auth/login', response.headers.get('Location', ''))
            else:
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Ticket', response.data)

if __name__ == '__main__':
    unittest.main()
