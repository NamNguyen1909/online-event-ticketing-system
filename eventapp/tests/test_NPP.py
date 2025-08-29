import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from flask import Flask
from flask_testing import TestCase
from flask_login import login_user
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
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 30, 'check_same_thread': False}}
        return app

    def create_user_and_commit(self, username, email, password, role=UserRole.customer, creator_id=None):
        """Helper để tạo và commit user, đảm bảo có ID hợp lệ."""
        with app.app_context():
            if db.session.query(User).filter_by(email=email).first():
                email = f"{uuid.uuid4().hex[:8]}@{email.split('@')[1]}"
            if db.session.query(User).filter_by(username=username).first():
                username = f"{username}_{uuid.uuid4().hex[:8]}"
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                creator_id=creator_id,
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
            return user

    def create_event_and_commit(self, organizer_id, title='Sự Kiện Kiểm Thử', is_active=True):
        """Helper để tạo và commit event, đảm bảo có ID hợp lệ."""
        with app.app_context():
            event = Event(
                organizer_id=organizer_id,
                title=title,
                description='Mô tả sự kiện',
                category=EventCategory.music,
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=2),
                location='Địa điểm kiểm thử',
                is_active=is_active
            )
            db.session.add(event)
            db.session.commit()
            db.session.refresh(event)
            return event

    def create_ticket_type_and_commit(self, event_id, name='VIP', price=100, total_quantity=50):
        """Helper để tạo và commit ticket type."""
        with app.app_context():
            ticket_type = TicketType(
                event_id=event_id,
                name=name,
                price=price,
                total_quantity=total_quantity,
                sold_quantity=0,
                is_active=True
            )
            db.session.add(ticket_type)
            db.session.commit()
            db.session.refresh(ticket_type)
            return ticket_type

    def create_ticket_and_commit(self, user_id, event_id, ticket_type_id):
        """Helper để tạo và commit ticket."""
        with app.app_context():
            ticket = Ticket(
                user_id=user_id,
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                is_paid=True,
                purchase_date=datetime.utcnow(),
                uuid=str(uuid.uuid4())
            )
            db.session.add(ticket)
            db.session.commit()
            db.session.refresh(ticket)
            return ticket

    def setUp(self):
        """Thiết lập cơ sở dữ liệu kiểm thử và môi trường."""
        with app.app_context():
            db.create_all()
            self.client = self.app.test_client()

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
                role=UserRole.staff,
                creator_id=self.organizer.id
            )

            self.event = self.create_event_and_commit(self.organizer.id)
            self.ticket_type = self.create_ticket_type_and_commit(self.event.id)
            self.ticket = self.create_ticket_and_commit(self.test_user.id, self.event.id, self.ticket_type.id)

            login_user(self.test_user)
            db.session.commit()

    def tearDown(self):
        """Dọn dẹp cơ sở dữ liệu kiểm thử."""
        with app.app_context():
            try:
                self.client.post('/auth/logout', follow_redirects=True)
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            except Exception as e:
                print(f"Error in tearDown: {e}")
                raise

    def login_user(self, username='testuser', password='StrongP@ss123'):
        """Hàm hỗ trợ đăng nhập người dùng."""
        with app.app_context():
            user = db.session.query(User).filter_by(username=username).first()
            if user:
                login_user(user)
                db.session.commit()
                db.session.refresh(user)
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
    """Kiểm thử đơn vị và tích hợp cho các hàm trong dao.py."""

    def test_event_creation_organizer_id_not_null(self):
        """Kiểm tra rằng sự kiện được tạo với organizer_id hợp lệ."""
        with app.app_context():
            self.assertIsNotNone(self.organizer.id, "Organizer ID should not be None after commit")
            self.assertEqual(self.event.organizer_id, self.organizer.id, "Event organizer_id should match organizer ID")
            self.assertEqual(db.session.query(Event).count(), 1, "Exactly one event should be created")

    @patch('eventapp.dao.User.query')
    def test_check_user_exists(self, mock_query):
        """Kiểm tra check_user với username tồn tại (unit test)."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_user('testuser')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once()

    def test_check_user_exists_integration(self):
        """Kiểm tra check_user với username tồn tại (integration test)."""
        with app.app_context():
            result = check_user('testuser')
            self.assertIsNotNone(result)
            self.assertEqual(result.id, self.test_user.id)

    @patch('eventapp.dao.User.query')
    def test_check_user_not_exists(self, mock_query):
        """Kiểm tra check_user với username không tồn tại (unit test)."""
        mock_query.filter.return_value.first.return_value = None
        result = check_user('nonexistent')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_check_email_exists(self, mock_query):
        """Kiểm tra check_email với email tồn tại (unit test)."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_email('test@example.com')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once()

    def test_check_email_exists_integration(self):
        """Kiểm tra check_email với email tồn tại (integration test)."""
        with app.app_context():
            result = check_email('test@example.com')
            self.assertIsNotNone(result)
            self.assertEqual(result.id, self.test_user.id)

    @patch('eventapp.dao.User.query')
    def test_check_email_not_exists(self, mock_query):
        """Kiểm tra check_email với email không tồn tại (unit test)."""
        mock_query.filter.return_value.first.return_value = None
        result = check_email('nonexistent@example.com')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_success(self, mock_query):
        """Kiểm tra get_user_events với người dùng hợp lệ và có sự kiện (unit test)."""
        mock_paginate = MagicMock()
        mock_paginate.items = [MagicMock(id=1, title='Sự Kiện Kiểm Thử')]
        mock_paginate.total = 1
        mock_paginate.has_next = False
        mock_paginate.has_prev = False
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.organizer.id)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, 'Sự Kiện Kiểm Thử')
        self.assertEqual(result.total, 1)
        mock_query.filter_by.assert_called_once_with(organizer_id=self.organizer.id)

    def test_get_user_events_success_integration(self):
        """Kiểm tra get_user_events với người dùng hợp lệ và có sự kiện (integration test)."""
        with app.app_context():
            result = get_user_events(self.organizer.id)
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].title, 'Sự Kiện Kiểm Thử')
            self.assertEqual(result.total, 1)

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_no_events(self, mock_query):
        """Kiểm tra get_user_events khi không có sự kiện (unit test)."""
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

    def test_create_event_with_tickets_invalid_tickets_rollback(self):
        """Kiểm tra create_event_with_tickets với ticket types không hợp lệ (unit test)."""
        with app.app_context():
            with patch('eventapp.dao.db.session.commit') as mock_commit:
                with patch('eventapp.dao.db.session.rollback') as mock_rollback:
                    mock_commit.side_effect = ValidationError("Invalid ticket type")
                    ticket_types = [{'name': 'VIP', 'price': -100, 'total_quantity': 50}]  # Giá âm
                    try:
                        create_event_with_tickets(
                            organizer_id=self.organizer.id,
                            title='Sự Kiện Không Hợp Lệ',
                            description='Mô tả',
                            category=EventCategory.music,
                            start_time=datetime.utcnow() + timedelta(days=1),
                            end_time=datetime.utcnow() + timedelta(days=2),
                            location='Địa điểm',
                            ticket_types=ticket_types
                        )
                    except ValidationError:
                        pass
                    mock_rollback.assert_called_once()
            self.assertEqual(db.session.query(Event).count(), 1)  # Không tạo thêm sự kiện
            self.assertEqual(db.session.query(TicketType).count(), 1)  # Không tạo thêm ticket type

    def test_create_event_with_tickets_invalid_tickets_rollback_integration(self):
        """Kiểm tra create_event_with_tickets với ticket types không hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                ticket_types = [{'name': 'VIP', 'price': -100, 'total_quantity': 50}]  # Giá âm
                try:
                    create_event_with_tickets(
                        organizer_id=self.organizer.id,
                        title='Sự Kiện Không Hợp Lệ',
                        description='Mô tả',
                        category=EventCategory.music,
                        start_time=datetime.utcnow() + timedelta(days=1),
                        end_time=datetime.utcnow() + timedelta(days=2),
                        location='Địa điểm',
                        ticket_types=ticket_types
                    )
                except ValidationError:
                    pass
            self.assertEqual(db.session.query(Event).count(), 1)  # Không tạo thêm sự kiện
            self.assertEqual(db.session.query(TicketType).count(), 1)  # Không tạo thêm ticket type

    def test_create_event_with_tickets_with_poster(self):
        """Kiểm tra create_event_with_tickets với poster (unit test)."""
        with app.app_context():
            with patch('eventapp.models.Event.upload_poster') as mock_upload:
                mock_upload.return_value = {'public_id': 'test_poster'}
                ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
                event = create_event_with_tickets(
                    organizer_id=self.organizer.id,
                    title='Sự Kiện Có Poster',
                    description='Mô tả',
                    category=EventCategory.music,
                    start_time=datetime.utcnow() + timedelta(days=1),
                    end_time=datetime.utcnow() + timedelta(days=2),
                    location='Địa điểm',
                    ticket_types=ticket_types,
                    poster_file=MagicMock()
                )
                self.assertIsNotNone(event)
                self.assertEqual(event.title, 'Sự Kiện Có Poster')
                self.assertEqual(event.poster, 'test_poster')
                mock_upload.assert_called_once()
                self.assertEqual(db.session.query(Event).count(), 2)
                self.assertEqual(db.session.query(TicketType).count(), 2)

    def test_create_event_with_tickets_with_poster_integration(self):
        """Kiểm tra create_event_with_tickets với poster (integration test)."""
        with app.app_context():
            ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
            event = create_event_with_tickets(
                organizer_id=self.organizer.id,
                title='Sự Kiện Có Poster',
                description='Mô tả',
                category=EventCategory.music,
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=2),
                location='Địa điểm',
                ticket_types=ticket_types
            )
            self.assertIsNotNone(event)
            self.assertEqual(event.title, 'Sự Kiện Có Poster')
            self.assertEqual(db.session.query(Event).count(), 2)
            self.assertEqual(db.session.query(TicketType).count(), 2)

    def test_delete_event_rollback_on_error(self):
        """Kiểm tra delete_event khi gặp lỗi (unit test)."""
        with app.app_context():
            with patch('eventapp.dao.db.session.commit') as mock_commit:
                with patch('eventapp.dao.db.session.rollback') as mock_rollback:
                    mock_commit.side_effect = IntegrityError("Mock integrity error", None, None)
                    try:
                        delete_event(self.event.id, self.organizer.id)
                    except IntegrityError:
                        pass
                    mock_rollback.assert_called_once()
            self.assertEqual(db.session.query(Event).count(), 1)  # Sự kiện không bị xóa

    def test_update_user_role_invalid_role_rollback(self):
        """Kiểm tra update_user_role với vai trò không hợp lệ (unit test)."""
        with app.app_context():
            with patch('eventapp.dao.db.session.commit') as mock_commit:
                with patch('eventapp.dao.db.session.rollback') as mock_rollback:
                    mock_commit.side_effect = ValueError('Vai trò không hợp lệ')
                    try:
                        update_user_role(self.test_user.id, 'invalid_role', self.organizer.id)
                    except ValueError:
                        pass
                    mock_rollback.assert_called_once()
            user = db.session.query(User).get(self.test_user.id)
            self.assertEqual(user.role, UserRole.customer)  # Vai trò không thay đổi

    def test_login_inactive_user(self):
        """Kiểm tra đăng nhập với người dùng không hoạt động (integration test)."""
        with app.app_context():
            inactive_user = self.create_user_and_commit(
                username='inactiveuser',
                email='inactive@example.com',
                password='StrongP@ss123',
                role=UserRole.customer
            )
            inactive_user.is_active = False
            db.session.commit()
            response = self.client.post('/auth/login', data={
                'username_or_email': 'inactiveuser',
                'password': 'StrongP@ss123',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(current_user.is_authenticated)

    def test_login_invalid_credentials(self):
        """Kiểm tra đăng nhập với thông tin không hợp lệ (integration test)."""
        with app.app_context():
            response = self.client.post('/auth/login', data={
                'username_or_email': 'testuser',
                'password': 'WrongPassword',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(current_user.is_authenticated)

    def test_login_success(self):
        """Kiểm tra đăng nhập thành công (integration test)."""
        with app.app_context():
            response = self.client.post('/auth/login', data={
                'username_or_email': 'testuser',
                'password': 'StrongP@ss123',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(current_user.is_authenticated)
            self.assertEqual(current_user.username, 'testuser')

    def test_logout_success(self):
        """Kiểm tra đăng xuất thành công (integration test)."""
        with app.app_context():
            self.login_user()
            response = self.client.post('/auth/logout', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(current_user.is_authenticated)

    def test_logout_unauthenticated(self):
        """Kiểm tra đăng xuất khi chưa đăng nhập (integration test)."""
        with app.app_context():
            self.client.post('/auth/logout', follow_redirects=True)
            response = self.client.get('/auth/check-auth')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['is_authenticated'], False)

    def test_register_duplicate_email_rollback(self):
        """Kiểm tra đăng ký với email trùng lặp (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                with patch('eventapp.auth.db.session.rollback') as mock_rollback:
                    response = self.client.post('/auth/register', data={
                        'username': 'newuser',
                        'email': 'test@example.com',
                        'password': 'StrongP@ss123',
                        'phone': '1234567890'
                    }, follow_redirects=True)
                    mock_rollback.assert_called_once()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(User).filter_by(email='test@example.com').count(), 1)

    def test_register_duplicate_username_rollback(self):
        """Kiểm tra đăng ký với username trùng lặp (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                with patch('eventapp.auth.db.session.rollback') as mock_rollback:
                    response = self.client.post('/auth/register', data={
                        'username': 'testuser',
                        'email': 'newuser@example.com',
                        'password': 'StrongP@ss123',
                        'phone': '1234567890'
                    }, follow_redirects=True)
                    mock_rollback.assert_called_once()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(User).filter_by(username='testuser').count(), 1)

    def test_create_event_invalid_end_time(self):
        """Kiểm tra POST /organizer/create-event với end_time không hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.organizer)
                db.session.commit()
                db.session.refresh(self.organizer)
                response = self.client.post('/organizer/create-event', data={
                    'title': '',
                    'description': 'Mô tả',
                    'category': 'music',
                    'start_time': '2025-09-01T12:00',
                    'end_time': '2025-09-01T10:00',
                    'location': 'Địa điểm'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(Event).count(), 1)
            self.assertEqual(db.session.query(TicketType).count(), 1)

    def test_create_event_integrity_error_rollback(self):
        """Kiểm tra POST /organizer/create-event khi gặp IntegrityError (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.organizer)
                db.session.commit()
                db.session.refresh(self.organizer)
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
                        mock_rollback.assert_called_once()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(Event).count(), 1)
            self.assertEqual(db.session.query(TicketType).count(), 1)

    def test_add_review_success(self):
        """Kiểm tra POST /event/<event_id>/review với dữ liệu hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
                response = self.client.post(f'/event/{self.event.id}/review', data={
                    'rating': 4,
                    'comment': 'Great event!'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            review = db.session.query(Review).filter_by(event_id=self.event.id, user_id=self.test_user.id).first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 4)
            self.assertEqual(review.comment, 'Great event!')
            self.assertEqual(db.session.query(Review).count(), 1)

    def test_add_review_unauthorized(self):
        """Kiểm tra POST /event/<event_id>/review khi không có quyền (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.organizer)
                db.session.commit()
                db.session.refresh(self.organizer)
                response = self.client.post(f'/event/{self.event.id}/review', data={
                    'rating': 4,
                    'comment': 'Great event!'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(db.session.query(Review).count(), 0)

    def test_add_review_invalid_rating_rollback(self):
        """Kiểm tra POST /event/<event_id>/review với rating không hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
                response = self.client.post(f'/event/{self.event.id}/review', data={
                    'rating': 6,
                    'comment': 'Great event!'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(Review).count(), 0)

    def test_reply_review_success(self):
        """Kiểm tra POST /review/<review_id>/reply với dữ liệu hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                review = Review(
                    event_id=self.event.id,
                    user_id=self.test_user.id,
                    rating=4,
                    comment='Great event!'
                )
                db.session.add(review)
                db.session.commit()
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.organizer)
                db.session.commit()
                db.session.refresh(self.organizer)
                response = self.client.post(f'/review/{review.id}/reply', data={
                    'reply_content': 'Thank you for your review!'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            reply = db.session.query(Review).filter_by(parent_review_id=review.id).first()
            self.assertIsNotNone(reply)
            self.assertEqual(reply.comment, 'Thank you for your review!')
            self.assertEqual(db.session.query(Review).count(), 2)

    def test_reply_review_unauthorized(self):
        """Kiểm tra POST /review/<review_id>/reply khi không có quyền (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                review = Review(
                    event_id=self.event.id,
                    user_id=self.test_user.id,
                    rating=4,
                    comment='Great event!'
                )
                db.session.add(review)
                db.session.commit()
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
                response = self.client.post(f'/review/{review.id}/reply', data={
                    'reply_content': 'Invalid reply'
                }, follow_redirects=True)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(db.session.query(Review).count(), 1)

    def test_process_booking_success(self):
        """Kiểm tra POST /booking/process với dữ liệu hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
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
            self.assertEqual(db.session.query(Ticket).count(), 3)

    def test_process_booking_no_tickets_rollback(self):
        """Kiểm tra POST /booking/process khi không chọn vé (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
                response = self.client.post('/booking/process', json={
                    'event_id': self.event.id,
                    'tickets': [],
                    'payment_method': 'cod'
                })
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertFalse(data.get('success'))
            self.assertEqual(data.get('message'), 'Vui lòng chọn ít nhất một loại vé.')
            self.assertEqual(db.session.query(Ticket).count(), 1)
            self.assertEqual(db.session.query(Payment).count(), 0)

    def test_process_booking_invalid_tickets_rollback(self):
        """Kiểm tra POST /booking/process với số lượng vé vượt quá tồn kho (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                db.session.refresh(self.test_user)
                login_user(self.test_user)
                db.session.commit()
                response = self.client.post('/booking/process', json={
                    'event_id': self.event.id,
                    'tickets': [{'ticket_type_id': self.ticket_type.id, 'quantity': 100}],
                    'payment_method': 'cod'
                })
            self.assertEqual(response.status_code, 200)
            data = response.json
            self.assertFalse(data.get('success'))
            self.assertIn('Không đủ vé loại VIP', data.get('message'))
            self.assertEqual(db.session.query(Ticket).count(), 1)
            self.assertEqual(db.session.query(Payment).count(), 0)

    def test_staff_scan_ticket_success(self):
        """Kiểm tra POST /staff/scan-ticket với vé hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.staff)
                db.session.commit()
                db.session.refresh(self.staff)
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
        """Kiểm tra POST /staff/scan-ticket với vé không hợp lệ (integration test)."""
        with app.app_context():
            with db.session.begin_nested():
                self.client.post('/auth/logout', follow_redirects=True)
                login_user(self.staff)
                db.session.commit()
                db.session.refresh(self.staff)
                response = self.client.post('/staff/scan-ticket', json={
                    'qr_data': 'invalid_uuid'
                })
            self.assertEqual(response.status_code, 404)
            data = response.json
            self.assertFalse(data.get('success'))
            self.assertEqual(data.get('message'), 'Vé không hợp lệ hoặc không tồn tại.')

if __name__ == '__main__':
    unittest.main()