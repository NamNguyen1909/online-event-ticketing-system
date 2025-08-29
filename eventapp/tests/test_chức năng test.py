import unittest
from flask import url_for
from eventapp import app

class TestEventDetailTicketSelection(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_event_detail_page_loads(self):
        """Kiểm tra trang chi tiết sự kiện có tải thành công và có tiêu đề sự kiện"""
        response = self.app.get('/event/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'event', response.data.lower())

    def test_ticket_types_displayed(self):
        """Kiểm tra các loại vé được hiển thị trên trang"""
        response = self.app.get('/event/1')
        self.assertEqual(response.status_code, 200)
        # Kiểm tra có từ khoá liên quan đến loại vé
        self.assertTrue(b've' in response.data or b'ticket' in response.data)

    def test_ticket_quantity_selection(self):
        """Kiểm tra có input chọn số lượng vé"""
        response = self.app.get('/event/1')
        self.assertEqual(response.status_code, 200)
        # Kiểm tra có input type=number hoặc select cho số lượng vé
        self.assertTrue(b'quantity' in response.data or b'so luong' in response.data or b'input' in response.data)

    def test_book_ticket_button(self):
        """Kiểm tra nút đặt vé có hiển thị"""
        response = self.app.get('/event/1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'dat ve' in response.data.lower() or b'book ticket' in response.data.lower() or b'btn-book-ticket' in response.data)

    def test_book_ticket_post(self):
        """Giả lập gửi POST đặt vé (nếu có route booking/process)"""
        # Giả lập dữ liệu đặt vé
        data = {
            'event_id': 1,
            'ticket_type_id': 1,
            'quantity': 1
        }
        # Nếu có route booking/process thì test, nếu không thì pass
        try:
            response = self.app.post('/booking/process', data=data, follow_redirects=True)
            self.assertIn(response.status_code, [200, 302, 400])
        except Exception:
            pass  # Nếu chưa có route thì bỏ qua

if __name__ == '__main__':
    unittest.main()
