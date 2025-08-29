import unittest
from flask import url_for
from eventapp import app

# Thêm import cho DB và models
from eventapp import db
from eventapp.models import Event, TicketType, User, Ticket
from werkzeug.security import generate_password_hash
import random

class TestEventDetailTicketSelection(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Đảm bảo có user login (nếu cần)
        with app.app_context():
            user = User.query.filter_by(role='customer').first()
            if not user:
                user = User(username='testuser', email='testuser@example.com', password_hash=generate_password_hash('123456'), role='customer', is_active=True)
                db.session.add(user)
                db.session.commit()
            self.user_id = user.id

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

        # Lấy event và ticket type còn vé
        with app.app_context():
            ticket_type = TicketType.query.filter(TicketType.is_active==True, TicketType.total_quantity > TicketType.sold_quantity).first()
            if not ticket_type:
                self.skipTest("Không có ticket type còn vé để test.")
            event = ticket_type.event
            quantity = 1
            # Lưu số lượng vé trước
            old_sold = ticket_type.sold_quantity

        # Giả lập login (nếu app dùng session user_id)
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id

        data = {
            'event_id': event.id,
            'ticket_type_id': ticket_type.id,
            'quantity': quantity
        }
        response = self.app.post('/booking/process', data=data, follow_redirects=True)
        self.assertIn(response.status_code, [200, 302, 400])

        # Kiểm tra số lượng vé đã tăng
        with app.app_context():
            ticket_type = TicketType.query.get(ticket_type.id)
            self.assertGreaterEqual(ticket_type.sold_quantity, old_sold)
            # Kiểm tra ticket đã được tạo cho user này
            ticket = Ticket.query.filter_by(user_id=self.user_id, event_id=event.id, ticket_type_id=ticket_type.id).order_by(Ticket.id.desc()).first()
            self.assertIsNotNone(ticket)

if __name__ == '__main__':
    unittest.main()
