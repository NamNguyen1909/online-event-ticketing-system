import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_testing import TestCase
from eventapp import app, db
from eventapp.models import User, UserRole, Event, TicketType, Review, EventCategory, Ticket, Payment
from eventapp.dao import (
    check_user, check_email, get_user_events, get_user_notifications,
    get_featured_events, get_event_detail, get_active_ticket_types,
    get_all_event_reviews, get_event_reviews, calculate_event_stats,
    get_user_review, user_can_review, create_event_with_tickets,
    validate_ticket_types, update_event, update_event_with_tickets,
    delete_event, bulk_delete_events, get_staff_by_organizer,
    get_customers_for_upgrade, get_staff_assigned_to_event, update_user_role
)
from eventapp.auth import validate_email, validate_password
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError

class EventHubTestCase(TestCase):
    """Lớp kiểm thử cơ bản cho ứng dụng EventHub với Flask test client."""

    def create_app(self):
        """Cấu hình ứng dụng Flask cho kiểm thử."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'test_secret'
        app.config['WTF_CSRF_ENABLED'] = False  # Tắt CSRF để kiểm thử
        return app

    def create_user_and_commit(self, username, email, password, role=UserRole.customer):
        """Helper để tạo và commit user, đảm bảo có ID hợp lệ."""
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        return user

    def setUp(self):
        """Thiết lập cơ sở dữ liệu kiểm thử và môi trường."""
        with app.app_context():
            db.create_all()
            self.client = self.app.test_client()

            # Bước 1: Tạo và commit dữ liệu cơ bản (User)
            self.test_user = self.create_user_and_commit(
                username='testuser',
                email='test@example.com',
                password='StrongP@ss123',
                role=UserRole.customer
            )
            self.organizer = self.create_user_and_commit(
                username='organizer',
                email='organizer@example.com',
                password='StrongP@ss123',
                role=UserRole.organizer
            )
            self.staff = self.create_user_and_commit(
                username='staffuser',
                email='staff@example.com',
                password='StrongP@ss123',
                role=UserRole.staff
            )

            # Bước 2: Tạo và commit dữ liệu phụ thuộc (Event, TicketType, Ticket)
            self.event = Event(
                id=1,
                organizer_id=self.organizer.id,
                title='Sự Kiện Kiểm Thử',
                description='Mô tả sự kiện',
                category=EventCategory.music,
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=2),
                location='Địa điểm kiểm thử',
                is_active=True
            )
            db.session.add(self.event)
            db.session.commit()

            self.ticket_type = TicketType(
                event_id=self.event.id,
                name='VIP',
                price=100,
                total_quantity=50,
                sold_quantity=0,
                is_active=True
            )
            self.ticket = Ticket(
                user_id=self.test_user.id,
                event_id=self.event.id,
                ticket_type_id=1,  # Sẽ cập nhật sau khi commit ticket_type
                is_paid=True,
                purchase_date=datetime.utcnow(),
                uuid=str(uuid.uuid4())
            )
            db.session.add_all([self.ticket_type, self.ticket])
            db.session.commit()
            self.ticket.ticket_type_id = self.ticket_type.id
            db.session.commit()

    def tearDown(self):
        """Dọn dẹp cơ sở dữ liệu kiểm thử."""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login_user(self, username='testuser', password='StrongP@ss123'):
        """Hàm hỗ trợ đăng nhập người dùng."""
        return self.client.post('/auth/login', data={
            'username_or_email': username,
            'password': password,
            'remember_me': True
        }, follow_redirects=True)

    def login_organizer(self):
        """Hàm hỗ trợ đăng nhập với vai trò tổ chức sự kiện."""
        return self.login_user('organizer', 'StrongP@ss123')

    def login_staff(self):
        """Hàm hỗ trợ đăng nhập với vai trò nhân viên."""
        return self.login_user('staffuser', 'StrongP@ss123')

class TestDAOLayer(EventHubTestCase):
    """Kiểm thử đơn vị cho các hàm trong dao.py."""

    def test_event_creation_organizer_id_not_null(self):
        """Kiểm tra rằng sự kiện được tạo với organizer_id hợp lệ."""
        self.assertIsNotNone(self.organizer.id, "Organizer ID should not be None after commit")
        self.assertEqual(self.event.organizer_id, self.organizer.id, "Event organizer_id should match organizer ID")
        self.assertEqual(db.session.query(Event).count(), 1, "Exactly one event should be created")

    @patch('eventapp.dao.User.query')
    def test_check_user_exists(self, mock_query):
        """Kiểm tra check_user với username tồn tại."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_user('testuser')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_check_user_not_exists(self, mock_query):
        """Kiểm tra check_user với username không tồn tại."""
        mock_query.filter.return_value.first.return_value = None
        result = check_user('nonexistent')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_check_email_exists(self, mock_query):
        """Kiểm tra check_email với email tồn tại."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_email('test@example.com')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_check_email_not_exists(self, mock_query):
        """Kiểm tra check_email với email không tồn tại."""
        mock_query.filter.return_value.first.return_value = None
        result = check_email('nonexistent@example.com')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_success(self, mock_query):
        """Kiểm tra get_user_events với người dùng hợp lệ và có sự kiện."""
        mock_paginate = MagicMock()
        mock_paginate.items = [self.event]
        mock_paginate.total = 1
        mock_paginate.has_next = False
        mock_paginate.has_prev = False
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.organizer.id)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, 'Sự Kiện Kiểm Thử')
        self.assertEqual(result.total, 1)
        mock_query.filter_by.assert_called_once_with(organizer_id=self.organizer.id)

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_no_events(self, mock_query):
        """Kiểm tra get_user_events khi không có sự kiện."""
        mock_paginate = MagicMock()
        mock_paginate.items = []
        mock_paginate.total = 0
        mock_paginate.has_next = False
        mock_paginate.has_prev = False
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.test_user.id)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(result.total, 0)
        mock_query.filter_by.assert_called_once_with(organizer_id=self.test_user.id)

    @patch('eventapp.dao.UserNotification.query')
    def test_get_user_notifications_success(self, mock_query):
        """Kiểm tra get_user_notifications với thông báo tồn tại."""
        mock_notification = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = [mock_notification]
        result = get_user_notifications(self.test_user.id)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(user_id=self.test_user.id)

    @patch('eventapp.dao.Event.query')
    def test_get_featured_events_success(self, mock_query):
        """Kiểm tra get_featured_events với giới hạn."""
        mock_query.filter_by.return_value.limit.return_value.all.return_value = [self.event]
        result = get_featured_events(limit=3)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(is_active=True)

    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_success(self, mock_query):
        """Kiểm tra get_event_detail với sự kiện hợp lệ."""
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = self.event
        result = get_event_detail(1)
        self.assertEqual(result, self.event)
        mock_query.return_value.options.assert_called_once()

    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_not_found(self, mock_query):
        """Kiểm tra get_event_detail với sự kiện không tồn tại."""
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = None
        result = get_event_detail(999)
        self.assertIsNone(result)

    @patch('eventapp.dao.TicketType.query')
    def test_get_active_ticket_types_success(self, mock_query):
        """Kiểm tra get_active_ticket_types với vé hoạt động."""
        mock_ticket = TicketType(id=1, event_id=1, is_active=True)
        mock_query.filter_by.return_value.all.return_value = [mock_ticket]
        result = get_active_ticket_types(1)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(event_id=1, is_active=True)

    @patch('eventapp.dao.db.session.query')
    def test_get_event_reviews_success(self, mock_query):
        """Kiểm tra get_event_reviews với đánh giá tồn tại."""
        mock_review = Review(id=1, event_id=1)
        mock_query.return_value.options.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_review]
        result = get_event_reviews(1, limit=5)
        self.assertEqual(len(result), 1)

    @patch('eventapp.dao.Review.query')
    def test_get_all_event_reviews_success(self, mock_query):
        """Kiểm tra get_all_event_reviews với đánh giá tồn tại."""
        mock_review = Review(id=1, event_id=1)
        mock_query.filter_by.return_value.all.return_value = [mock_review]
        result = get_all_event_reviews(1)
        self.assertEqual(len(result), 1)

    def test_calculate_event_stats(self):
        """Kiểm tra calculate_event_stats với dữ liệu hợp lệ."""
        ticket_types = [MagicMock(total_quantity=100, sold_quantity=50, price=10000)]
        reviews = [MagicMock(rating=4)]
        stats = calculate_event_stats(ticket_types, reviews)
        self.assertEqual(stats['total_tickets'], 100)
        self.assertEqual(stats['sold_tickets'], 50)
        self.assertEqual(stats['available_tickets'], 50)
        self.assertEqual(stats['revenue'], 500000)
        self.assertEqual(stats['average_rating'], 4.0)

    @patch('eventapp.dao.Review.query')
    def test_get_user_review_success(self, mock_query):
        """Kiểm tra get_user_review với đánh giá tồn tại."""
        mock_review = Review(id=1, event_id=1, user_id=self.test_user.id)
        mock_query.filter_by.return_value.first.return_value = mock_review
        result = get_user_review(1, self.test_user.id)
        self.assertEqual(result, mock_review)

    @patch('eventapp.dao.Review.query')
    def test_get_user_review_not_found(self, mock_query):
        """Kiểm tra get_user_review khi không có đánh giá."""
        mock_query.filter_by.return_value.first.return_value = None
        result = get_user_review(1, self.test_user.id)
        self.assertIsNone(result)

    @patch('eventapp.dao.User.query')
    @patch('eventapp.dao.Ticket.query')
    @patch('eventapp.dao.get_user_review')
    def test_user_can_review_yes(self, mock_get_user_review, mock_ticket_query, mock_user_query):
        """Kiểm tra user_can_review khi người dùng có thể đánh giá."""
        mock_user = MagicMock()
        mock_user.id = self.test_user.id
        mock_user.role = UserRole.customer
        mock_user_query.get.return_value = mock_user
        mock_ticket_query.filter_by.return_value.first.return_value = MagicMock(is_paid=True)
        mock_get_user_review.return_value = None
        result = user_can_review(1, self.test_user.id)
        self.assertTrue(result)

    @patch('eventapp.dao.User.query')
    def test_user_can_review_not_customer(self, mock_user_query):
        """Kiểm tra user_can_review khi người dùng không phải là khách hàng."""
        mock_user = MagicMock()
        mock_user.id = 999
        mock_user.role = UserRole.organizer
        mock_user_query.get.return_value = mock_user
        result = user_can_review(1, 999)
        self.assertFalse(result)

    @patch('eventapp.dao.User.query')
    @patch('eventapp.dao.Ticket.query')
    @patch('eventapp.dao.get_user_review')
    def test_user_can_review_already_reviewed(self, mock_get_user_review, mock_ticket_query, mock_user_query):
        """Kiểm tra user_can_review khi người dùng đã đánh giá."""
        mock_user = MagicMock()
        mock_user.id = self.test_user.id
        mock_user.role = UserRole.customer
        mock_user_query.get.return_value = mock_user
        mock_ticket_query.filter_by.return_value.first.return_value = MagicMock(is_paid=True)
        mock_get_user_review.return_value = MagicMock()
        result = user_can_review(1, self.test_user.id)
        self.assertFalse(result)

    @patch('eventapp.dao.db.session')
    @patch('eventapp.dao.Event.upload_poster')
    def test_create_event_with_tickets_with_poster(self, mock_upload_poster, mock_session):
        """Kiểm tra create_event_with_tickets với dữ liệu hợp lệ có poster."""
        data = {
            'title': 'Sự Kiện Kiểm Thử',
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T10:00',
            'end_time': '2025-09-01T12:00',
            'location': 'Địa điểm kiểm thử',
            'poster': 'test_poster.jpg',
            'ticket_types': [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        }
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.flush.return_value = None
        mock_upload_poster.return_value = {'public_id': 'test_poster_id'}
        result = create_event_with_tickets(self.organizer.id, data)
        self.assertIsNotNone(result)
        mock_upload_poster.assert_called_once()
        self.assertEqual(db.session.query(Event).count(), 2)  # 1 từ setUp, 1 từ test
        self.assertEqual(db.session.query(TicketType).count(), 2)  # 1 từ setUp, 1 từ test

    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_invalid_tickets_rollback(self, mock_session):
        """Kiểm tra create_event_with_tickets với loại vé không hợp lệ, đảm bảo rollback."""
        data = {
            'title': 'Sự Kiện Kiểm Thử',
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T10:00',
            'end_time': '2025-09-01T12:00',
            'location': 'Địa điểm kiểm thử',
            'ticket_types': [{'name': 'VIP', 'price': -100, 'total_quantity': 50}]
        }
        mock_session.rollback = MagicMock()
        with pytest.raises(ValidationError) as exc_info:
            create_event_with_tickets(self.organizer.id, data)
        self.assertIn('Giá vé "VIP" phải không âm', str(exc_info.value))
        mock_session.rollback.assert_called_once()
        self.assertEqual(db.session.query(Event).count(), 1)  # Không thêm event mới
        self.assertEqual(db.session.query(TicketType).count(), 1)  # Không thêm ticket type mới

    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_integrity_error_rollback(self, mock_session):
        """Kiểm tra create_event_with_tickets khi gặp IntegrityError, đảm bảo rollback."""
        data = {
            'title': 'Sự Kiện Kiểm Thử',
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T10:00',
            'end_time': '2025-09-01T12:00',
            'location': 'Địa điểm kiểm thử',
            'ticket_types': [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        }
        mock_session.commit.side_effect = IntegrityError("Mock integrity error", None, None)
        mock_session.rollback = MagicMock()
        with pytest.raises(IntegrityError) as exc_info:
            create_event_with_tickets(self.organizer.id, data)
        self.assertIn("Mock integrity error", str(exc_info.value))
        mock_session.rollback.assert_called_once()
        self.assertEqual(db.session.query(Event).count(), 1)
        self.assertEqual(db.session.query(TicketType).count(), 1)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_success(self, mock_query):
        """Kiểm tra delete_event với sự kiện hợp lệ."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.organizer_id = self.organizer.id
        mock_event.is_active = True
        mock_query.get.return_value = mock_event
        result = delete_event(1, self.organizer.id)
        self.assertIsNone(result)
        self.assertFalse(mock_event.is_active)
        mock_query.get.assert_called_once_with(1)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_unauthorized(self, mock_query):
        """Kiểm tra delete_event với người dùng không có quyền."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.organizer_id = 999
        mock_query.get.return_value = mock_event
        with pytest.raises(ValueError) as exc_info:
            delete_event(1, self.test_user.id)
        self.assertEqual(str(exc_info.value), 'Event not found or not owned by user')

    @patch('eventapp.dao.Event.query')
    @patch('eventapp.dao.db.session')
    def test_delete_event_rollback_on_error(self, mock_session, mock_query):
        """Kiểm tra delete_event rollback khi gặp lỗi."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.organizer_id = self.organizer.id
        mock_query.get.return_value = mock_event
        mock_session.commit.side_effect = IntegrityError("Mock error", None, None)
        mock_session.rollback = MagicMock()
        with pytest.raises(IntegrityError) as exc_info:
            delete_event(1, self.organizer.id)
        self.assertIn("Mock error", str(exc_info.value))
        mock_session.rollback.assert_called_once()
        self.assertEqual(db.session.query(Event).count(), 1)

    @patch('eventapp.dao.User.query')
    def test_get_staff_by_organizer_success(self, mock_query):
        """Kiểm tra get_staff_by_organizer với nhân viên hợp lệ."""
        mock_staff = MagicMock()
        mock_staff.id = self.staff.id
        mock_staff.role = UserRole.staff
        mock_staff.creator_id = self.organizer.id
        mock_query.filter.return_value.all.return_value = [mock_staff]
        result = get_staff_by_organizer(self.organizer.id)
        self.assertEqual(len(result), 1)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_get_customers_for_upgrade_success(self, mock_query):
        """Kiểm tra get_customers_for_upgrade với khách hàng hợp lệ."""
        mock_customer = MagicMock()
        mock_customer.id = self.test_user.id
        mock_customer.role = UserRole.customer
        mock_customer.creator_id = None
        mock_query.filter.return_value.all.return_value = [mock_customer]
        result = get_customers_for_upgrade()
        self.assertEqual(len(result), 1)

    @patch('eventapp.dao.Event.query')
    def test_get_staff_assigned_to_event_success(self, mock_query):
        """Kiểm tra get_staff_assigned_to_event với sự kiện hợp lệ."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.organizer_id = self.organizer.id
        mock_query.get.return_value = mock_event
        result = get_staff_assigned_to_event(1, self.organizer.id)
        self.assertEqual(result, mock_event)

    @patch('eventapp.dao.Event.query')
    def test_get_staff_assigned_to_event_unauthorized(self, mock_query):
        """Kiểm tra get_staff_assigned_to_event với người dùng không có quyền."""
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.organizer_id = 999
        mock_query.get.return_value = mock_event
        result = get_staff_assigned_to_event(1, self.test_user.id)
        self.assertIsNone(result)

    @patch('eventapp.dao.User.query')
    def test_update_user_role_to_staff(self, mock_query):
        """Kiểm tra update_user_role sang vai trò nhân viên."""
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.role = UserRole.customer
        mock_user.creator_id = None
        mock_query.get.return_value = mock_user
        update_user_role(2, 'staff', self.organizer.id)
        self.assertEqual(mock_user.role, UserRole.staff)
        self.assertEqual(mock_user.creator_id, self.organizer.id)

    @patch('eventapp.dao.User.query')
    @patch('eventapp.dao.db.session')
    def test_update_user_role_invalid_role_rollback(self, mock_session, mock_query):
        """Kiểm tra update_user_role với vai trò không hợp lệ, đảm bảo rollback."""
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.role = UserRole.customer
        mock_user.creator_id = None
        mock_query.get.return_value = mock_user
        mock_session.rollback = MagicMock()
        with pytest.raises(ValueError) as exc_info:
            update_user_role(2, 'invalid_role', self.organizer.id)
        self.assertEqual(str(exc_info.value), 'Vai trò không hợp lệ')
        self.assertEqual(mock_user.role, UserRole.customer)
        self.assertIsNone(mock_user.creator_id)
        mock_session.rollback.assert_called_once()

class TestAuthLayer(EventHubTestCase):
    """Kiểm thử đơn vị và tích hợp cho các hàm trong auth.py."""

    def test_validate_email_valid(self):
        """Kiểm tra validate_email với email hợp lệ."""
        result = validate_email('test@example.com')
        self.assertTrue(result)

    def test_validate_email_invalid(self):
        """Kiểm tra validate_email với email không hợp lệ."""
        result = validate_email('invalid_email')
        self.assertFalse(result)

    def test_validate_password_strong(self):
        """Kiểm tra validate_password với mật khẩu mạnh."""
        is_valid, message = validate_password('StrongP@ss123')
        self.assertTrue(is_valid)
        self.assertEqual(message, '')

    def test_validate_password_weak_length(self):
        """Kiểm tra validate_password với mật khẩu quá ngắn."""
        is_valid, message = validate_password('weak')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải dài ít nhất 8 ký tự')

    def test_validate_password_no_uppercase(self):
        """Kiểm tra validate_password không có chữ in hoa."""
        is_valid, message = validate_password('weakpass123!')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải chứa ít nhất một chữ cái in hoa')

    def test_validate_password_no_lowercase(self):
        """Kiểm tra validate_password không có chữ thường."""
        is_valid, message = validate_password('WEAKPASS123!')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải chứa ít nhất một chữ cái thường')

    def test_validate_password_no_number(self):
        """Kiểm tra validate_password không có số."""
        is_valid, message = validate_password('WeakPass!')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải chứa ít nhất một số')

    def test_validate_password_no_special_char(self):
        """Kiểm tra validate_password không có ký tự đặc biệt."""
        is_valid, message = validate_password('WeakPass123')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải chứa ít nhất một ký tự đặc biệt')

    def test_register_success(self):
        """Kiểm tra đăng ký với dữ liệu hợp lệ."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongP@ss123',
            'phone': '1234567890'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        user = db.session.query(User).filter_by(username='newuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.role, UserRole.customer)
        self.assertEqual(db.session.query(User).count(), 4)  # 3 từ setUp, 1 từ đăng ký

    def test_register_duplicate_username_rollback(self):
        """Kiểm tra đăng ký với username đã tồn tại, đảm bảo rollback."""
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'newuser@example.com',
            'password': 'StrongP@ss123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register.html', response.data)
        self.assertEqual(db.session.query(User).count(), 3)  # Không thêm user mới

    def test_register_duplicate_email_rollback(self):
        """Kiểm tra đăng ký với email đã tồn tại, đảm bảo rollback."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'test@example.com',
            'password': 'StrongP@ss123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register.html', response.data)
        self.assertEqual(db.session.query(User).count(), 3)

    def test_register_invalid_email(self):
        """Kiểm tra đăng ký với email không hợp lệ."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'invalid_email',
            'password': 'StrongP@ss123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register.html', response.data)
        self.assertEqual(db.session.query(User).count(), 3)

    def test_register_weak_password(self):
        """Kiểm tra đăng ký với mật khẩu yếu."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'weak'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'register.html', response.data)
        self.assertEqual(db.session.query(User).count(), 3)

    def test_login_success(self):
        """Kiểm tra đăng nhập với thông tin hợp lệ."""
        response = self.login_user()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'index.html', response.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(int(sess.get('_user_id')), self.test_user.id)

    def test_login_invalid_credentials(self):
        """Kiểm tra đăng nhập với thông tin không hợp lệ."""
        response = self.client.post('/auth/login', data={
            'username_or_email': 'testuser',
            'password': 'wrong_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login.html', response.data)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('_user_id'))

    def test_login_inactive_user(self):
        """Kiểm tra đăng nhập với người dùng không hoạt động."""
        self.test_user.is_active = False
        db.session.commit()
        response = self.login_user()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login.html', response.data)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('_user_id'))

    def test_logout_success(self):
        """Kiểm tra đăng xuất khi đã đăng nhập."""
        self.login_user()
        response = self.client.post('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'index.html', response.data)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('_user_id'))

    def test_logout_unauthenticated(self):
        """Kiểm tra đăng xuất khi chưa đăng nhập."""
        response = self.client.post('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login.html', response.data)

    def test_check_auth_authenticated(self):
        """Kiểm tra /check-auth khi đã đăng nhập."""
        self.login_user()
        response = self.client.get('/auth/check-auth')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data.get('is_authenticated'))
        self.assertEqual(data.get('user', {}).get('username'), 'testuser')

    def test_check_auth_unauthenticated(self):
        """Kiểm tra /check-auth khi chưa đăng nhập."""
        response = self.client.get('/auth/check-auth')
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertFalse(data.get('is_authenticated'))

class TestEventRoutes(EventHubTestCase):
    """Kiểm thử tích hợp cho các endpoint trong routes.py liên quan đến sự kiện."""

    def test_get_index(self):
        """Kiểm tra GET / endpoint."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'index.html', response.data)

    def test_get_events(self):
        """Kiểm tra GET /events endpoint."""
        response = self.client.get('/events')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EventList.html', response.data)

    def test_get_event_detail(self):
        """Kiểm tra GET /event/<event_id> endpoint."""
        response = self.client.get('/event/1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EventDetail.html', response.data)

    def test_get_event_detail_not_found(self):
        """Kiểm tra GET /event/<event_id> với sự kiện không tồn tại."""
        response = self.client.get('/event/999', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EventList.html', response.data)

    def test_get_organizer_events(self):
        """Kiểm tra GET /organizer/my-events endpoint."""
        self.login_organizer()
        response = self.client.get('/organizer/my-events')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'my_events.html', response.data)

    def test_get_organizer_events_unauthorized(self):
        """Kiểm tra GET /organizer/my-events khi chưa đăng nhập."""
        response = self.client.get('/organizer/my-events', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login.html', response.data)

    def test_create_event_success(self):
        """Kiểm tra POST /organizer/create-event endpoint."""
        self.login_organizer()
        response = self.client.post('/organizer/create-event', data={
            'title': 'Sự Kiện Mới',
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T10:00',
            'end_time': '2025-09-01T12:00',
            'location': 'Địa điểm',
            'ticket_name': 'VIP',
            'price': 100,
            'ticket_quantity': 50
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        event = db.session.query(Event).filter_by(title='Sự Kiện Mới').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.organizer_id, self.organizer.id)
        ticket_type = db.session.query(TicketType).filter_by(event_id=event.id).first()
        self.assertIsNotNone(ticket_type)
        self.assertEqual(ticket_type.name, 'VIP')
        self.assertEqual(db.session.query(Event).count(), 2)  # 1 từ setUp, 1 từ test
        self.assertEqual(db.session.query(TicketType).count(), 2)

    def test_create_event_invalid_data_rollback(self):
        """Kiểm tra POST /organizer/create-event với dữ liệu không hợp lệ."""
        self.login_organizer()
        response = self.client.post('/organizer/create-event', data={
            'title': '',  # Không hợp lệ: tiêu đề rỗng
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T12:00',
            'end_time': '2025-09-01T10:00',  # Không hợp lệ: end_time trước start_time
            'location': 'Địa điểm'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'create_event.html', response.data)
        self.assertEqual(db.session.query(Event).count(), 1)  # Không thêm event mới
        self.assertEqual(db.session.query(TicketType).count(), 1)

    def test_create_event_integrity_error_rollback(self):
        """Kiểm tra POST /organizer/create-event khi gặp IntegrityError."""
        self.login_organizer()
        with patch('eventapp.routes.db.session.commit') as mock_commit:
            mock_commit.side_effect = IntegrityError("Mock integrity error", None, None)
            with patch('eventapp.routes.db.session.rollback') as mock_rollback:
                response = self.client.post('/organizer/create-event', data={
                    'title': 'Sự Kiện Mới',
                    'description': 'Mô tả',
                    'category': 'music',
                    'start_time': '2025-09-01T10:00',
                    'end_time': '2025-09-01T12:00',
                    'location': 'Địa điểm',
                    'ticket_name': 'VIP',
                    'price': 100,
                    'ticket_quantity': 50
                }, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                mock_rollback.assert_called_once()
                self.assertEqual(db.session.query(Event).count(), 1)
                self.assertEqual(db.session.query(TicketType).count(), 1)

    def test_add_review_success(self):
        """Kiểm tra POST /event/<event_id>/review với dữ liệu hợp lệ."""
        self.login_user()
        response = self.client.post('/event/1/review', data={
            'rating': 4,
            'comment': 'Great event!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        review = db.session.query(Review).filter_by(event_id=1, user_id=self.test_user.id).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, 'Great event!')
        self.assertEqual(db.session.query(Review).count(), 1)

    def test_add_review_unauthorized(self):
        """Kiểm tra POST /event/<event_id>/review khi không có quyền."""
        self.login_organizer()
        response = self.client.post('/event/1/review', data={
            'rating': 4,
            'comment': 'Great event!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(db.session.query(Review).count(), 0)

    def test_add_review_invalid_rating_rollback(self):
        """Kiểm tra POST /event/<event_id>/review với rating không hợp lệ."""
        self.login_user()
        response = self.client.post('/event/1/review', data={
            'rating': 6,  # Không hợp lệ
            'comment': 'Great event!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'EventDetail.html', response.data)
        self.assertEqual(db.session.query(Review).count(), 0)  # Không thêm review

    def test_reply_review_success(self):
        """Kiểm tra POST /review/<review_id>/reply với dữ liệu hợp lệ."""
        review = Review(
            event_id=self.event.id,
            user_id=self.test_user.id,
            rating=4,
            comment='Great event!'
        )
        db.session.add(review)
        db.session.commit()
        self.login_organizer()
        response = self.client.post(f'/review/{review.id}/reply', data={
            'reply_content': 'Thank you for your review!'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        reply = db.session.query(Review).filter_by(parent_review_id=review.id).first()
        self.assertIsNotNone(reply)
        self.assertEqual(reply.comment, 'Thank you for your review!')
        self.assertEqual(db.session.query(Review).count(), 2)

    def test_reply_review_unauthorized(self):
        """Kiểm tra POST /review/<review_id>/reply khi không có quyền."""
        review = Review(
            event_id=self.event.id,
            user_id=self.test_user.id,
            rating=4,
            comment='Great event!'
        )
        db.session.add(review)
        db.session.commit()
        self.login_user()
        response = self.client.post(f'/review/{review.id}/reply', data={
            'reply_content': 'Invalid reply'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(db.session.query(Review).count(), 1)  # Chỉ có review gốc

    def test_process_booking_success(self):
        """Kiểm tra POST /booking/process với dữ liệu hợp lệ."""
        self.login_user()
        response = self.client.post('/booking/process', json={
            'event_id': self.event.id,
            'tickets': [{'ticket_type_id': self.ticket_type.id, 'quantity': 2}],
            'payment_method': 'cod',
            'subtotal': 200,
            'discount_amount': 0,
            'total_amount': 200
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data.get('success'))
        payment = db.session.query(Payment).filter_by(user_id=self.test_user.id).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, 200)
        self.assertEqual(db.session.query(Ticket).count(), 3)  # 1 từ setUp, 2 từ booking

    def test_process_booking_no_tickets_rollback(self):
        """Kiểm tra POST /booking/process khi không chọn vé."""
        self.login_user()
        response = self.client.post('/booking/process', json={
            'event_id': self.event.id,
            'tickets': [],
            'payment_method': 'cod'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('message'), 'Vui lòng chọn ít nhất một loại vé.')
        self.assertEqual(db.session.query(Ticket).count(), 1)  # Không thêm ticket mới
        self.assertEqual(db.session.query(Payment).count(), 0)

    def test_process_booking_invalid_tickets_rollback(self):
        """Kiểm tra POST /booking/process với số lượng vé vượt quá tồn kho."""
        self.login_user()
        response = self.client.post('/booking/process', json={
            'event_id': self.event.id,
            'tickets': [{'ticket_type_id': self.ticket_type.id, 'quantity': 100}],
            'payment_method': 'cod'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertFalse(data.get('success'))
        self.assertIn('Không đủ vé loại VIP', data.get('message'))
        self.assertEqual(db.session.query(Ticket).count(), 1)  # Không thêm ticket mới
        self.assertEqual(db.session.query(Payment).count(), 0)

    def test_staff_scan_ticket_success(self):
        """Kiểm tra POST /staff/scan-ticket với vé hợp lệ."""
        self.login_staff()
        response = self.client.post('/staff/scan-ticket', json={
            'qr_data': self.ticket.uuid
        })
        self.assertEqual(response.status_code, 200)
        data = response.json
        self.assertTrue(data.get('success'))
        self.assertIn('Check-in thành công', data.get('message'))
        ticket = db.session.query(Ticket).get(self.ticket.id)
        self.assertTrue(ticket.is_checked_in)

    def test_staff_scan_ticket_invalid(self):
        """Kiểm tra POST /staff/scan-ticket với vé không hợp lệ."""
        self.login_staff()
        response = self.client.post('/staff/scan-ticket', json={
            'qr_data': 'invalid_uuid'
        })
        self.assertEqual(response.status_code, 404)
        data = response.json
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('message'), 'Vé không hợp lệ hoặc không tồn tại.')

if __name__ == '__main__':
    unittest.main()