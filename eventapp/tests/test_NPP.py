import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_testing import TestCase
from eventapp import app, db
from eventapp.models import User, UserRole, Event, TicketType, Review, EventCategory
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

class EventHubTestCase(TestCase):
    """Lớp kiểm thử cơ bản cho ứng dụng EventHub với Flask test client."""

    def create_app(self):
        """Cấu hình ứng dụng Flask cho kiểm thử."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'test_secret'
        return app

    def setUp(self):
        """Thiết lập cơ sở dữ liệu kiểm thử và môi trường."""
        db.create_all()
        self.client = self.app.test_client()
        # Tạo người dùng kiểm thử
        self.test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash='hashed_password',
            role=UserRole.customer
        )
        db.session.add(self.test_user)
        db.session.commit()

    def tearDown(self):
        """Dọn dẹp cơ sở dữ liệu kiểm thử."""
        db.session.remove()
        db.drop_all()

class TestDAOLayer(EventHubTestCase):
    """Kiểm thử đơn vị cho các hàm trong dao.py."""

    @patch('eventapp.dao.User.query')
    def test_check_user_exists(self, mock_query):
        """Kiểm tra check_user với username tồn tại."""
        mock_query.filter.return_value.first.return_value = self.test_user
        result = check_user('testuser')
        self.assertEqual(result, self.test_user)
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
        mock_query.filter.return_value.first.return_value = self.test_user
        result = check_email('test@example.com')
        self.assertEqual(result, self.test_user)
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
        mock_event = Event(id=1, organizer_id=self.test_user.id, title='Sự Kiện Kiểm Thử')
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = [mock_event]
        result = get_user_events(self.test_user.id)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, 'Sự Kiện Kiểm Thử')

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_no_events(self, mock_query):
        """Kiểm tra get_user_events khi không có sự kiện."""
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = []
        result = get_user_events(self.test_user.id)
        self.assertEqual(len(result.items), 0)

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
        mock_event = Event(id=1, is_active=True)
        mock_query.filter_by.return_value.limit.return_value.all.return_value = [mock_event]
        result = get_featured_events(limit=3)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(is_active=True)

    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_success(self, mock_query):
        """Kiểm tra get_event_detail với sự kiện hợp lệ."""
        mock_event = Event(id=1, is_active=True)
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = mock_event
        result = get_event_detail(1)
        self.assertEqual(result, mock_event)

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
        mock_user_query.get.return_value = self.test_user
        mock_ticket_query.filter_by.return_value.first.return_value = MagicMock(is_paid=True)
        mock_get_user_review.return_value = None
        result = user_can_review(1, self.test_user.id)
        self.assertTrue(result)

    @patch('eventapp.dao.User.query')
    def test_user_can_review_not_customer(self, mock_user_query):
        """Kiểm tra user_can_review khi người dùng không phải là khách hàng."""
        mock_user = User(role=UserRole.organizer)
        mock_user_query.get.return_value = mock_user
        result = user_can_review(1, mock_user.id)
        self.assertFalse(result)

    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_success(self, mock_session):
        """Kiểm tra create_event_with_tickets với dữ liệu hợp lệ."""
        data = {
            'title': 'Sự Kiện Kiểm Thử',
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T10:00',
            'end_time': '2025-09-01T12:00',
            'location': 'Địa điểm kiểm thử',
            'ticket_types': [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        }
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        result = create_event_with_tickets(data, self.test_user.id)
        self.assertIsNotNone(result)

    def test_validate_ticket_types_duplicate(self):
        """Kiểm tra validate_ticket_types với tên vé trùng lặp."""
        ticket_types = [
            {'name': 'VIP', 'price': 100, 'total_quantity': 50},
            {'name': 'VIP', 'price': 200, 'total_quantity': 30}
        ]
        with self.assertRaises(ValidationError):
            validate_ticket_types(ticket_types)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_success(self, mock_query):
        """Kiểm tra delete_event với sự kiện và người dùng hợp lệ."""
        mock_event = Event(id=1, organizer_id=self.test_user.id)
        mock_query.get.return_value = mock_event
        result = delete_event(1, self.test_user.id)
        self.assertTrue(result)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_unauthorized(self, mock_query):
        """Kiểm tra delete_event với người dùng không có quyền."""
        mock_event = Event(id=1, organizer_id=999)
        mock_query.get.return_value = mock_event
        result = delete_event(1, self.test_user.id)
        self.assertFalse(result)

    @patch('eventapp.dao.User.query')
    def test_get_staff_by_organizer_success(self, mock_query):
        """Kiểm tra get_staff_by_organizer với nhân viên hợp lệ."""
        mock_staff = User(role=UserRole.staff, creator_id=self.test_user.id)
        mock_query.filter.return_value.filter.return_value.all.return_value = [mock_staff]
        result = get_staff_by_organizer(self.test_user.id)
        self.assertEqual(len(result), 1)

    @patch('eventapp.dao.User.query')
    def test_get_customers_for_upgrade_success(self, mock_query):
        """Kiểm tra get_customers_for_upgrade với khách hàng hợp lệ."""
        mock_customer = User(role=UserRole.customer, creator_id=None)
        mock_query.filter.return_value.filter.return_value.all.return_value = [mock_customer]
        result = get_customers_for_upgrade()
        self.assertEqual(len(result), 1)

    @patch('eventapp.dao.Event.query')
    def test_get_staff_assigned_to_event_success(self, mock_query):
        """Kiểm tra get_staff_assigned_to_event với sự kiện hợp lệ."""
        mock_event = Event(id=1, organizer_id=self.test_user.id)
        mock_query.get.return_value = mock_event
        result = get_staff_assigned_to_event(1, self.test_user.id)
        self.assertEqual(result, mock_event)

    @patch('eventapp.dao.User.query')
    def test_update_user_role_to_staff(self, mock_query):
        """Kiểm tra update_user_role sang vai trò nhân viên."""
        mock_user = User(id=2, role=UserRole.customer, creator_id=None)
        mock_query.get.return_value = mock_user
        update_user_role(2, 'staff', self.test_user.id)
        self.assertEqual(mock_user.role, UserRole.staff)
        self.assertEqual(mock_user.creator_id, self.test_user.id)

class TestAuthLayer(EventHubTestCase):
    """Kiểm thử đơn vị cho các hàm trong auth.py."""

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

    def test_validate_password_weak(self):
        """Kiểm tra validate_password với mật khẩu yếu."""
        is_valid, message = validate_password('weak')
        self.assertFalse(is_valid)
        self.assertEqual(message, 'Mật khẩu phải dài ít nhất 8 ký tự')

class TestRoutes(EventHubTestCase):
    """Kiểm thử tích hợp cho các endpoint trong routes.py."""

    def setUp(self):
        """Thiết lập dữ liệu kiểm thử cho các route."""
        super().setUp()
        # Tạo người dùng tổ chức sự kiện
        self.organizer = User(
            username='organizer',
            email='organizer@example.com',
            password_hash=generate_password_hash('StrongP@ss123'),
            role=UserRole.organizer
        )
        db.session.add(self.organizer)
        # Tạo sự kiện
        self.event = Event(
            id=1,
            organizer_id=self.organizer.id,
            title='Sự Kiện Kiểm Thử',
            description='Mô tả',
            category=EventCategory.music,
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=2),
            location='Địa điểm kiểm thử',
            is_active=True
        )
        db.session.add(self.event)
        db.session.commit()

    def login_organizer(self):
        """Hàm hỗ trợ đăng nhập với vai trò tổ chức sự kiện."""
        self.client.post('/auth/login', data={
            'username_or_email': 'organizer',
            'password': 'StrongP@ss123',
            'remember_me': True
        })

    def test_get_index(self):
        """Kiểm tra GET / endpoint."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_get_events(self):
        """Kiểm tra GET /events endpoint."""
        response = self.client.get('/events')
        self.assertEqual(response.status_code, 200)

    def test_get_event_detail(self):
        """Kiểm tra GET /event/<event_id> endpoint."""
        response = self.client.get('/event/1')
        self.assertEqual(response.status_code, 200)

    def test_get_event_detail_not_found(self):
        """Kiểm tra GET /event/<event_id> với sự kiện không tồn tại."""
        response = self.client.get('/event/999')
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến /events

    def test_get_organizer_events(self):
        """Kiểm tra GET /organizer/my-events endpoint."""
        self.login_organizer()
        response = self.client.get('/organizer/my-events')
        self.assertEqual(response.status_code, 200)

    def test_get_organizer_events_unauthorized(self):
        """Kiểm tra GET /organizer/my-events khi chưa đăng nhập."""
        response = self.client.get('/organizer/my-events')
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến đăng nhập

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
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng khi thành công

    def test_create_event_invalid_data(self):
        """Kiểm tra POST /organizer/create-event với dữ liệu không hợp lệ."""
        self.login_organizer()
        response = self.client.post('/organizer/create-event', data={
            'title': '',  # Không hợp lệ: tiêu đề rỗng
            'description': 'Mô tả',
            'category': 'music',
            'start_time': '2025-09-01T12:00',  # Không hợp lệ: end_time trước start_time
            'end_time': '2025-09-01T10:00',
            'location': 'Địa điểm'
        })
        self.assertEqual(response.status_code, 200)  # Ở lại form với lỗi

    def test_get_login(self):
        """Kiểm tra GET /auth/login endpoint."""
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)

    def test_post_login_success(self):
        """Kiểm tra POST /auth/login với thông tin hợp lệ."""
        response = self.client.post('/auth/login', data={
            'username_or_email': 'organizer',
            'password': 'StrongP@ss123',
            'remember_me': True
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến index

    def test_post_login_invalid(self):
        """Kiểm tra POST /auth/login với thông tin không hợp lệ."""
        response = self.client.post('/auth/login', data={
            'username_or_email': 'organizer',
            'password': 'wrong_password'
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến login

    def test_get_register(self):
        """Kiểm tra GET /auth/register endpoint."""
        response = self.client.get('/auth/register')
        self.assertEqual(response.status_code, 200)

    def test_post_register_success(self):
        """Kiểm tra POST /auth/register với dữ liệu hợp lệ."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongP@ss123',
            'phone': '1234567890'
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến index

    def test_post_register_invalid_email(self):
        """Kiểm tra POST /auth/register với email không hợp lệ."""
        response = self.client.post('/auth/register', data={
            'username': 'newuser',
            'email': 'invalid_email',
            'password': 'StrongP@ss123'
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng đến register

    def test_update_user_role_success(self):
        """Kiểm tra POST /organizer/update-role/<user_id> endpoint."""
        self.login_organizer()
        new_user = User(
            id=2,
            username='newuser',
            email='newuser@example.com',
            password_hash='hashed_password',
            role=UserRole.customer
        )
        db.session.add(new_user)
        db.session.commit()
        response = self.client.post('/organizer/update-role/2', data={
            'role': 'staff'
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng khi thành công

    def test_assign_staff_success(self):
        """Kiểm tra POST /organizer/assign-staff/<event_id> endpoint."""
        self.login_organizer()
        staff = User(
            id=2,
            username='staffuser',
            email='staff@example.com',
            password_hash='hashed_password',
            role=UserRole.staff,
            creator_id=self.organizer.id
        )
        db.session.add(staff)
        db.session.commit()
        response = self.client.post('/organizer/assign-staff/1', data={
            'staff_id': 2
        })
        self.assertEqual(response.status_code, 302)  # Chuyển hướng khi thành công

if __name__ == '__main__':
    unittest.main()