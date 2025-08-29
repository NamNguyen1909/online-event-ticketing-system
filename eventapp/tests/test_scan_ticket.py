import unittest
from eventapp import app, db
from eventapp.models import User, Event, TicketType, Ticket
from werkzeug.security import generate_password_hash
import uuid

class TestScanTicket(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        with app.app_context():
            # Tạo user staff
            staff = User.query.filter_by(role='staff').first()
            if not staff:
                staff = User(username='staff_scan', email='staff_scan@example.com', password_hash=generate_password_hash('123456'), role='staff', is_active=True)
                db.session.add(staff)
                db.session.commit()
            self.staff_id = staff.id
            # Tạo user customer
            customer = User.query.filter_by(role='customer').first()
            if not customer:
                customer = User(username='customer_scan', email='customer_scan@example.com', password_hash=generate_password_hash('123456'), role='customer', is_active=True)
                db.session.add(customer)
                db.session.commit()
            # Tạo event và ticket type
            event = Event.query.first()
            if not event:
                event = Event(organizer_id=staff.id, title='Scan Event', description='...', category='music', start_time='2025-08-29 10:00:00', end_time='2025-08-29 12:00:00', location='Test', is_active=True)
                db.session.add(event)
                db.session.commit()
            ticket_type = TicketType.query.filter_by(event_id=event.id).first()
            if not ticket_type:
                ticket_type = TicketType(event_id=event.id, name='QR', price=100, total_quantity=10, sold_quantity=0, is_active=True)
                db.session.add(ticket_type)
                db.session.commit()
            # Tạo ticket với uuid giả
            self.fake_uuid = str(uuid.uuid4())
            ticket = Ticket.query.filter_by(uuid=self.fake_uuid).first()
            if not ticket:
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
            Ticket.query.filter_by(id=self.ticket_id).delete()
            db.session.commit()
