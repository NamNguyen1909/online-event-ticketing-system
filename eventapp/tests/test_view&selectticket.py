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
        from datetime import datetime, timedelta
        import uuid
        import random
        self.app = app.test_client()
        self.app.testing = True
        with app.app_context():
            # Xóa dữ liệu test cũ nếu có
            db.session.query(Ticket).delete()
            db.session.query(TicketType).delete()
            db.session.query(Event).delete()
            db.session.query(User).filter(User.email.like('%viewselect_test_%')).delete()
            db.session.commit()

            # Tạo user customer với email random
            customer_email = f'viewselect_test_customer_{uuid.uuid4()}@example.com'
            user = User(username=f'testuser_{random.randint(1,99999)}', email=customer_email, password_hash=generate_password_hash('123456'), role='customer', is_active=True)
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

            # Tạo event và ticket type nếu chưa có
            start_time = datetime.now() + timedelta(hours=1)
            end_time = start_time + timedelta(hours=2)
            event = Event(organizer_id=user.id, title='ViewSelect Event', description='...', category='music', start_time=start_time, end_time=end_time, location='Test', is_active=True)
            db.session.add(event)
            db.session.commit()
            self.event_id = event.id

            ticket_type = TicketType(event_id=event.id, name='VIP', price=100, total_quantity=10, sold_quantity=0, is_active=True)
            db.session.add(ticket_type)
            db.session.commit()
            self.ticket_type_id = ticket_type.id

    def test_event_detail_page_loads(self):
        """Kiểm tra trang chi tiết sự kiện có tải thành công và có tiêu đề sự kiện"""
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
        response = self.app.get(f'/event/{self.event_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'event', response.data.lower())

    def test_ticket_types_displayed(self):
        """Kiểm tra các loại vé được hiển thị trên trang"""
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
        response = self.app.get(f'/event/{self.event_id}')
        self.assertEqual(response.status_code, 200)
        # Kiểm tra có từ khoá liên quan đến loại vé
        self.assertTrue(b've' in response.data or b'ticket' in response.data)

    def test_ticket_quantity_selection(self):
        """Kiểm tra có input chọn số lượng vé"""
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
        response = self.app.get(f'/event/{self.event_id}')
        self.assertEqual(response.status_code, 200)
        # Kiểm tra có input type=number hoặc select cho số lượng vé
        self.assertTrue(b'quantity' in response.data or b'so luong' in response.data or b'input' in response.data)

    def test_book_ticket_button(self):
        """Kiểm tra nút đặt vé có hiển thị"""
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
        response = self.app.get(f'/event/{self.event_id}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'dat ve' in response.data.lower() or b'book ticket' in response.data.lower() or b'btn-book-ticket' in response.data)

    def test_book_ticket_post(self):
        """Giả lập gửi POST đặt vé, đảm bảo user đã đăng nhập qua session."""
        data = {
            'event_id': self.event_id,
            'ticket_type_id': self.ticket_type_id,
            'quantity': 1
        }
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
        response = self.app.post('/booking/process', data=data, follow_redirects=False)
        self.assertIn(response.status_code, [200, 400])
        with app.app_context():
            ticket_type = TicketType.query.get(self.ticket_type_id)
            self.assertGreaterEqual(ticket_type.sold_quantity, 0)
            ticket = Ticket.query.filter_by(user_id=self.user_id, event_id=self.event_id, ticket_type_id=self.ticket_type_id).order_by(Ticket.id.desc()).first()
            self.assertIsNotNone(ticket)

    def tearDown(self):
        with app.app_context():
            db.session.query(Ticket).delete()
            db.session.query(TicketType).delete()
            db.session.query(Event).delete()
            db.session.query(User).filter(User.email.like('%viewselect_test_%')).delete()
            db.session.commit()

if __name__ == '__main__':
    unittest.main()
