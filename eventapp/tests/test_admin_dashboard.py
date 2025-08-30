import unittest
from eventapp.app import app

class TestAdminDashboard(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_admin_dashboard_access(self):
        # Giả lập đăng nhập admin bằng session
        with self.app as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = '1'  # Thay bằng id admin thực tế
            response = c.get('/admin/dashboard', follow_redirects=False)
            if response.status_code == 302:
                self.assertIn('/auth/login', response.headers.get('Location', ''))
            else:
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Admin', response.data)

if __name__ == '__main__':
    unittest.main()
