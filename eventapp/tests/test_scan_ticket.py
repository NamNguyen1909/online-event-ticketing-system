import unittest
from eventapp import app, db
from eventapp.models import User, Event, TicketType, Ticket
from werkzeug.security import generate_password_hash
import uuid

class TestScanTicket(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        from datetime import datetime, timedelta
        import random
        with app.app_context():
            # Xóa dữ liệu test cũ nếu có
            db.session.query(Ticket).delete()
            db.session.query(TicketType).delete()
            db.session.query(Event).delete()
            db.session.query(User).filter(User.email.like('%scan_test_%')).delete()
            db.session.commit()

            # Tạo user staff với email random
            staff_email = f'scan_test_staff_{uuid.uuid4()}@example.com'
            staff = User(username=f'staff_scan_{random.randint(1,99999)}', email=staff_email, password_hash=generate_password_hash('123456'), role='staff', is_active=True)
            db.session.add(staff)
            db.session.commit()
            self.staff_id = staff.id

            # Tạo user customer với email random
            customer_email = f'scan_test_customer_{uuid.uuid4()}@example.com'
            customer = User(username=f'customer_scan_{random.randint(1,99999)}', email=customer_email, password_hash=generate_password_hash('123456'), role='customer', is_active=True)
            db.session.add(customer)
            db.session.commit()

            # Tạo event và ticket type
            start_time = datetime.now() + timedelta(hours=1)
            end_time = start_time + timedelta(hours=2)
            event = Event(organizer_id=staff.id, title='Scan Event', description='...', category='music', start_time=start_time, end_time=end_time, location='Test', is_active=True)
            db.session.add(event)
            db.session.commit()

            ticket_type = TicketType(event_id=event.id, name='QR', price=100, total_quantity=10, sold_quantity=0, is_active=True)
            db.session.add(ticket_type)
            db.session.commit()

            # Tạo ticket với uuid giả
            self.fake_uuid = str(uuid.uuid4())
            ticket = Ticket(user_id=customer.id, event_id=event.id, ticket_type_id=ticket_type.id, uuid=self.fake_uuid, is_paid=True)
            db.session.add(ticket)
            db.session.commit()
            self.ticket_id = ticket.id

            # Sinh QR code và upload cloudinary (nếu có hàm generate_qr_code)
            if hasattr(ticket, 'generate_qr_code'):
                ticket.generate_qr_code()
                db.session.commit()
            self.qr_data = self.fake_uuid

    def test_scan_ticket_api(self):
        # Giả lập login staff
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.staff_id
        # Gửi POST với qr_data là uuid
        response = self.app.post('/staff/scan-ticket', json={'qr_data': self.qr_data})
        self.assertIn(response.status_code, [200, 201])
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('message', data)
        self.assertIn(self.qr_data, data.get('message', ''))

    def tearDown(self):
        with app.app_context():
            db.session.query(Ticket).delete()
            db.session.query(TicketType).delete()
            db.session.query(Event).delete()
            db.session.query(User).filter(User.email.like('%scan_test_%')).delete()
            db.session.commit()
