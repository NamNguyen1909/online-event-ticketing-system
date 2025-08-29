import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_testing import TestCase
from flask_login import login_user, logout_user, current_user
from eventapp import app, db
from eventapp.models import User, UserRole, Event, TicketType, Review, EventCategory, Ticket
from eventapp.dao import (
    check_user, check_email, get_user_events, get_user_notifications,
    get_featured_events, get_event_detail, get_active_ticket_types,
    get_all_event_reviews, get_event_reviews, calculate_event_stats,
    get_user_review, user_can_review, create_event_with_tickets,
    validate_ticket_types, update_event, update_event_with_tickets,
    delete_event, bulk_delete_events, get_staff_by_organizer,
    get_customers_for_upgrade, get_staff_assigned_to_event, update_user_role
)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import uuid
from sqlalchemy.exc import IntegrityError
from wtforms.validators import ValidationError

class EventHubTestCase(TestCase):
    """Base test class for EventHub application with Flask test client."""

    def create_app(self):
        """Configure Flask app for testing."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'test_secret'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 30, 'check_same_thread': False}}
        return app

    def create_user_and_commit(self, username, email, password, role=UserRole.customer, creator_id=None, is_active=True):
        """Helper to create and commit a user with unique username/email."""
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
                is_active=is_active
            )
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
            return user

    def create_event_and_commit(self, organizer_id, title='Test Event', is_active=True):
        """Helper to create and commit an event."""
        with app.app_context():
            event = Event(
                organizer_id=organizer_id,
                title=title,
                description='Test description',
                category=EventCategory.music,
                start_time=datetime.utcnow() + timedelta(days=1),
                end_time=datetime.utcnow() + timedelta(days=2),
                location='Test location',
                is_active=is_active
            )
            db.session.add(event)
            db.session.commit()
            db.session.refresh(event)
            return event

    def create_ticket_type_and_commit(self, event_id, name='VIP', price=100, total_quantity=50):
        """Helper to create and commit a ticket type."""
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
        """Helper to create and commit a ticket."""
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
        """Set up test database and environment."""
        with app.app_context():
            db.create_all()
            self.client = self.app.test_client()

            # Create test users
            self.customer = self.create_user_and_commit(
                username='customer',
                email='customer@example.com',
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
                username='staff',
                email='staff@example.com',
                password='StrongP@ss123',
                role=UserRole.staff,
                creator_id=self.organizer.id
            )

            # Create test event and ticket
            self.event = self.create_event_and_commit(self.organizer.id)
            self.ticket_type = self.create_ticket_type_and_commit(self.event.id)
            self.ticket = self.create_ticket_and_commit(self.customer.id, self.event.id, self.ticket_type.id)

    def tearDown(self):
        """Clean up test database."""
        with app.app_context():
            try:
                self.client.post('/auth/logout', follow_redirects=True)
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
            except Exception as e:
                print(f"Error in tearDown: {e}")
                raise

    def login_user(self, username, password):
        """Helper to log in a user."""
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

class TestDAOLayer(EventHubTestCase):
    """Unit tests for DAO layer functions."""

    # Tests for check_user
    @patch('eventapp.dao.User.query')
    def test_check_user_success(self, mock_query):
        """Test check_user with existing username."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_user('customer')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once_with(User.username == 'customer')

    @patch('eventapp.dao.User.query')
    def test_check_user_not_exists(self, mock_query):
        """Test check_user with non-existing username."""
        mock_query.filter.return_value.first.return_value = None
        result = check_user('nonexistent')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once_with(User.username == 'nonexistent')

    def test_check_user_integration(self):
        """Integration test for check_user with existing username."""
        with app.app_context():
            result = check_user('customer')
            self.assertIsNotNone(result)
            self.assertEqual(result.id, self.customer.id)

    # Tests for check_email
    @patch('eventapp.dao.User.query')
    def test_check_email_success(self, mock_query):
        """Test check_email with existing email."""
        mock_user = MagicMock()
        mock_user.id = 1
        mock_query.filter.return_value.first.return_value = mock_user
        result = check_email('customer@example.com')
        self.assertEqual(result, mock_user)
        mock_query.filter.assert_called_once_with(User.email == 'customer@example.com')

    @patch('eventapp.dao.User.query')
    def test_check_email_not_exists(self, mock_query):
        """Test check_email with non-existing email."""
        mock_query.filter.return_value.first.return_value = None
        result = check_email('nonexistent@example.com')
        self.assertIsNone(result)
        mock_query.filter.assert_called_once_with(User.email == 'nonexistent@example.com')

    def test_check_email_integration(self):
        """Integration test for check_email with existing email."""
        with app.app_context():
            result = check_email('customer@example.com')
            self.assertIsNotNone(result)
            self.assertEqual(result.id, self.customer.id)

    # Tests for get_user_events
    @patch('eventapp.dao.Event.query')
    def test_get_user_events_success(self, mock_query):
        """Test get_user_events with existing events."""
        mock_paginate = MagicMock()
        mock_paginate.items = [MagicMock(id=1, title='Test Event')]
        mock_paginate.total = 1
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.organizer.id)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, 'Test Event')
        mock_query.filter_by.assert_called_once_with(organizer_id=self.organizer.id)

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_no_events(self, mock_query):
        """Test get_user_events with no events."""
        mock_paginate = MagicMock()
        mock_paginate.items = []
        mock_paginate.total = 0
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.customer.id)
        self.assertEqual(len(result.items), 0)
        self.assertEqual(result.total, 0)
        mock_query.filter_by.assert_called_once_with(organizer_id=self.customer.id)

    def test_get_user_events_integration(self):
        """Integration test for get_user_events with existing events."""
        with app.app_context():
            result = get_user_events(self.organizer.id)
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].title, 'Test Event')

    # Tests for get_user_notifications
    @patch('eventapp.dao.UserNotification.query')
    def test_get_user_notifications_success(self, mock_query):
        """Test get_user_notifications with notifications."""
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = [MagicMock(id=1)]
        result = get_user_notifications(self.customer.id)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(user_id=self.customer.id)

    @patch('eventapp.dao.UserNotification.query')
    def test_get_user_notifications_empty(self, mock_query):
        """Test get_user_notifications with no notifications."""
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = []
        result = get_user_notifications(self.customer.id)
        self.assertEqual(len(result), 0)
        mock_query.filter_by.assert_called_once_with(user_id=self.customer.id)

    # Tests for get_featured_events
    @patch('eventapp.dao.Event.query')
    def test_get_featured_events_success(self, mock_query):
        """Test get_featured_events with active events."""
        mock_query.filter_by.return_value.limit.return_value.all.return_value = [MagicMock(id=1)]
        result = get_featured_events(limit=3)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(is_active=True)

    @patch('eventapp.dao.Event.query')
    def test_get_featured_events_no_events(self, mock_query):
        """Test get_featured_events with no active events."""
        mock_query.filter_by.return_value.limit.return_value.all.return_value = []
        result = get_featured_events(limit=3)
        self.assertEqual(len(result), 0)
        mock_query.filter_by.assert_called_once_with(is_active=True)

    # Tests for get_event_detail
    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_success(self, mock_query):
        """Test get_event_detail with valid event ID."""
        mock_event = MagicMock(id=1)
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = mock_event
        result = get_event_detail(1)
        self.assertEqual(result, mock_event)
        mock_query.return_value.options.return_value.filter_by.assert_called_once_with(id=1, is_active=True)

    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_not_found(self, mock_query):
        """Test get_event_detail with non-existing event ID."""
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = None
        result = get_event_detail(999)
        self.assertIsNone(result)
        mock_query.return_value.options.return_value.filter_by.assert_called_once_with(id=999, is_active=True)

    # Tests for get_active_ticket_types
    @patch('eventapp.dao.TicketType.query')
    def test_get_active_ticket_types_success(self, mock_query):
        """Test get_active_ticket_types with active tickets."""
        mock_query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
        result = get_active_ticket_types(self.event.id)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, is_active=True)

    @patch('eventapp.dao.TicketType.query')
    def test_get_active_ticket_types_empty(self, mock_query):
        """Test get_active_ticket_types with no active tickets."""
        mock_query.filter_by.return_value.all.return_value = []
        result = get_active_ticket_types(self.event.id)
        self.assertEqual(len(result), 0)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, is_active=True)

    # Tests for get_all_event_reviews
    @patch('eventapp.dao.Review.query')
    def test_get_all_event_reviews_success(self, mock_query):
        """Test get_all_event_reviews with reviews."""
        mock_query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
        result = get_all_event_reviews(self.event.id)
        self.assertEqual(len(result), 1)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, parent_review_id=None)

    @patch('eventapp.dao.Review.query')
    def test_get_all_event_reviews_empty(self, mock_query):
        """Test get_all_event_reviews with no reviews."""
        mock_query.filter_by.return_value.all.return_value = []
        result = get_all_event_reviews(self.event.id)
        self.assertEqual(len(result), 0)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, parent_review_id=None)

    # Tests for get_event_reviews
    @patch('eventapp.dao.db.session.query')
    def test_get_event_reviews_success(self, mock_query):
        """Test get_event_reviews with limited reviews."""
        mock_query.return_value.options.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = [MagicMock(id=1)]
        result = get_event_reviews(self.event.id, limit=5)
        self.assertEqual(len(result), 1)
        mock_query.return_value.options.return_value.filter_by.assert_called_once_with(event_id=self.event.id, parent_review_id=None)

    @patch('eventapp.dao.db.session.query')
    def test_get_event_reviews_empty(self, mock_query):
        """Test get_event_reviews with no reviews."""
        mock_query.return_value.options.return_value.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = get_event_reviews(self.event.id, limit=5)
        self.assertEqual(len(result), 0)
        mock_query.return_value.options.return_value.filter_by.assert_called_once_with(event_id=self.event.id, parent_review_id=None)

    # Tests for calculate_event_stats
    def test_calculate_event_stats_success(self):
        """Test calculate_event_stats with valid data."""
        ticket_types = [MagicMock(total_quantity=100, sold_quantity=50, price=200)]
        reviews = [MagicMock(rating=4), MagicMock(rating=5)]
        stats = calculate_event_stats(ticket_types, reviews)
        self.assertEqual(stats['total_tickets'], 100)
        self.assertEqual(stats['sold_tickets'], 50)
        self.assertEqual(stats['available_tickets'], 50)
        self.assertEqual(stats['revenue'], 10000)
        self.assertEqual(stats['average_rating'], 4.5)
        self.assertEqual(stats['review_count'], 2)

    def test_calculate_event_stats_empty(self):
        """Test calculate_event_stats with no data."""
        stats = calculate_event_stats([], [])
        self.assertEqual(stats['total_tickets'], 0)
        self.assertEqual(stats['sold_tickets'], 0)
        self.assertEqual(stats['available_tickets'], 0)
        self.assertEqual(stats['revenue'], 0)
        self.assertEqual(stats['average_rating'], 0)
        self.assertEqual(stats['review_count'], 0)

    # Tests for get_user_review
    @patch('eventapp.dao.Review.query')
    def test_get_user_review_success(self, mock_query):
        """Test get_user_review with existing review."""
        mock_review = MagicMock(id=1)
        mock_query.filter_by.return_value.first.return_value = mock_review
        result = get_user_review(self.event.id, self.customer.id)
        self.assertEqual(result, mock_review)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, user_id=self.customer.id, parent_review_id=None)

    @patch('eventapp.dao.Review.query')
    def test_get_user_review_not_found(self, mock_query):
        """Test get_user_review with no review."""
        mock_query.filter_by.return_value.first.return_value = None
        result = get_user_review(self.event.id, self.customer.id)
        self.assertIsNone(result)
        mock_query.filter_by.assert_called_once_with(event_id=self.event.id, user_id=self.customer.id, parent_review_id=None)

    # Tests for user_can_review
    @patch('eventapp.dao.User.query')
    @patch('eventapp.dao.Ticket.query')
    @patch('eventapp.dao.get_user_review')
    def test_user_can_review_success(self, mock_get_user_review, mock_ticket_query, mock_user_query):
        """Test user_can_review for customer with ticket and no review."""
        mock_user = MagicMock(role=UserRole.customer)
        mock_user_query.get.return_value = mock_user
        mock_ticket_query.filter_by.return_value.first.return_value = MagicMock()
        mock_get_user_review.return_value = None
        result = user_can_review(self.event.id, self.customer.id)
        self.assertTrue(result)
        mock_user_query.get.assert_called_once_with(self.customer.id)
        mock_ticket_query.filter_by.assert_called_once_with(user_id=self.customer.id, event_id=self.event.id, is_paid=True)
        mock_get_user_review.assert_called_once_with(self.event.id, self.customer.id)

    @patch('eventapp.dao.User.query')
    def test_user_can_review_not_customer(self, mock_user_query):
        """Test user_can_review for non-customer user."""
        mock_user = MagicMock(role=UserRole.organizer)
        mock_user_query.get.return_value = mock_user
        result = user_can_review(self.event.id, self.organizer.id)
        self.assertFalse(result)
        mock_user_query.get.assert_called_once_with(self.organizer.id)

    # Tests for create_event_with_tickets
    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_success(self, mock_db_session):
        """Test create_event_with_tickets with valid data."""
        data = {
            'title': 'New Event',
            'description': 'Description',
            'category': 'music',
            'start_time': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'end_time': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'location': 'Location'
        }
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        event = create_event_with_tickets(self.organizer.id, data['title'], data['description'],
                                         EventCategory[data['category']], datetime.fromisoformat(data['start_time']),
                                         datetime.fromisoformat(data['end_time']), data['location'], ticket_types)
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called_once()
        self.assertIsNotNone(event)
        self.assertEqual(event.title, 'New Event')

    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_invalid_tickets(self, mock_db_session):
        """Test create_event_with_tickets with invalid ticket types."""
        data = {
            'title': 'New Event',
            'description': 'Description',
            'category': 'music',
            'start_time': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'end_time': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'location': 'Location'
        }
        ticket_types = [{'name': 'VIP', 'price': -100, 'total_quantity': 50}]
        mock_db_session.commit.side_effect = ValidationError("Invalid price")
        with self.assertRaises(ValidationError):
            create_event_with_tickets(self.organizer.id, data['title'], data['description'],
                                     EventCategory[data['category']], datetime.fromisoformat(data['start_time']),
                                     datetime.fromisoformat(data['end_time']), data['location'], ticket_types)
        mock_db_session.rollback.assert_called_once()

    # Tests for validate_ticket_types
    def test_validate_ticket_types_success(self):
        """Test validate_ticket_types with valid ticket types."""
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        validate_ticket_types(ticket_types)
        # No exception means success

    def test_validate_ticket_types_duplicate_names(self):
        """Test validate_ticket_types with duplicate ticket names."""
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50},
                        {'name': 'VIP', 'price': 200, 'total_quantity': 30}]
        with self.assertRaises(ValidationError):
            validate_ticket_types(ticket_types)

    def test_validate_ticket_types_negative_price(self):
        """Test validate_ticket_types with negative price."""
        ticket_types = [{'name': 'VIP', 'price': -100, 'total_quantity': 50}]
        with self.assertRaises(ValidationError):
            validate_ticket_types(ticket_types)

    # Tests for update_event
    @patch('eventapp.dao.Event.query')
    def test_update_event_success(self, mock_query):
        """Test update_event with valid data."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.get.return_value = mock_event
        data = {'title': 'Updated Event'}
        result = update_event(self.event.id, data, self.organizer.id)
        self.assertEqual(result, mock_event)
        mock_event.title = 'Updated Event'
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_update_event_not_found(self, mock_query):
        """Test update_event with non-existing event."""
        mock_query.get.return_value = None
        data = {'title': 'Updated Event'}
        result = update_event(999, data, self.organizer.id)
        self.assertIsNone(result)
        mock_query.get.assert_called_once_with(999)

    # Tests for update_event_with_tickets
    @patch('eventapp.dao.Event.query')
    def test_update_event_with_tickets_success(self, mock_query):
        """Test update_event_with_tickets with valid data."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.get.return_value = mock_event
        data = {'title': 'Updated Event'}
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        result = update_event_with_tickets(self.event.id, data, self.organizer.id, ticket_types)
        self.assertEqual(result, mock_event)
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_update_event_with_tickets_not_found(self, mock_query):
        """Test update_event_with_tickets with non-existing event."""
        mock_query.get.return_value = None
        data = {'title': 'Updated Event'}
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        result = update_event_with_tickets(999, data, self.organizer.id, ticket_types)
        self.assertIsNone(result)
        mock_query.get.assert_called_once_with(999)

    # Tests for delete_event
    @patch('eventapp.dao.Event.query')
    def test_delete_event_success(self, mock_query):
        """Test delete_event with valid event."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.get.return_value = mock_event
        result = delete_event(self.event.id, self.organizer.id)
        self.assertTrue(result)
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_not_found(self, mock_query):
        """Test delete_event with non-existing event."""
        mock_query.get.return_value = None
        result = delete_event(999, self.organizer.id)
        self.assertFalse(result)
        mock_query.get.assert_called_once_with(999)

    # Tests for bulk_delete_events
    @patch('eventapp.dao.Event.query')
    def test_bulk_delete_events_success(self, mock_query):
        """Test bulk_delete_events with valid events."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.filter.return_value.all.return_value = [mock_event]
        result = bulk_delete_events([self.event.id], self.organizer.id)
        self.assertTrue(result)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.Event.query')
    def test_bulk_delete_events_no_events(self, mock_query):
        """Test bulk_delete_events with no valid events."""
        mock_query.filter.return_value.all.return_value = []
        result = bulk_delete_events([999], self.organizer.id)
        self.assertFalse(result)
        mock_query.filter.assert_called_once()

    # Tests for get_staff_by_organizer
    @patch('eventapp.dao.User.query')
    def test_get_staff_by_organizer_success(self, mock_query):
        """Test get_staff_by_organizer with staff members."""
        mock_query.filter.return_value.all.return_value = [MagicMock(id=1)]
        result = get_staff_by_organizer(self.organizer.id)
        self.assertEqual(len(result), 1)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_get_staff_by_organizer_empty(self, mock_query):
        """Test get_staff_by_organizer with no staff."""
        mock_query.filter.return_value.all.return_value = []
        result = get_staff_by_organizer(self.organizer.id)
        self.assertEqual(len(result), 0)
        mock_query.filter.assert_called_once()

    # Tests for get_customers_for_upgrade
    @patch('eventapp.dao.User.query')
    def test_get_customers_for_upgrade_success(self, mock_query):
        """Test get_customers_for_upgrade with customers."""
        mock_query.filter.return_value.all.return_value = [MagicMock(id=1)]
        result = get_customers_for_upgrade()
        self.assertEqual(len(result), 1)
        mock_query.filter.assert_called_once()

    @patch('eventapp.dao.User.query')
    def test_get_customers_for_upgrade_empty(self, mock_query):
        """Test get_customers_for_upgrade with no customers."""
        mock_query.filter.return_value.all.return_value = []
        result = get_customers_for_upgrade()
        self.assertEqual(len(result), 0)
        mock_query.filter.assert_called_once()

    # Tests for get_staff_assigned_to_event
    @patch('eventapp.dao.Event.query')
    def test_get_staff_assigned_to_event_success(self, mock_query):
        """Test get_staff_assigned_to_event with valid event."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.get.return_value = mock_event
        result = get_staff_assigned_to_event(self.event.id, self.organizer.id)
        self.assertEqual(result, mock_event)
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_get_staff_assigned_to_event_not_found(self, mock_query):
        """Test get_staff_assigned_to_event with non-existing event."""
        mock_query.get.return_value = None
        result = get_staff_assigned_to_event(999, self.organizer.id)
        self.assertIsNone(result)
        mock_query.get.assert_called_once_with(999)

    # Tests for update_user_role
    @patch('eventapp.dao.User.query')
    def test_update_user_role_success(self, mock_query):
        """Test update_user_role to staff role."""
        mock_user = MagicMock(role=UserRole.customer)
        mock_query.get.return_value = mock_user
        update_user_role(self.customer.id, 'staff', self.organizer.id)
        self.assertEqual(mock_user.role, UserRole.staff)
        self.assertEqual(mock_user.creator_id, self.organizer.id)
        mock_query.get.assert_called_once_with(self.customer.id)

    @patch('eventapp.dao.User.query')
    def test_update_user_role_invalid_role(self, mock_query):
        """Test update_user_role with invalid role."""
        mock_query.get.return_value = MagicMock(role=UserRole.customer)
        with self.assertRaises(ValueError):
            update_user_role(self.customer.id, 'invalid_role', self.organizer.id)
        mock_query.get.assert_called_once_with(self.customer.id)

class TestRoutesIntegration(EventHubTestCase):
    """Integration tests for routes in routes.py."""

    def test_get_index(self):
        """Test GET / (home page)."""
        with app.app_context():
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'index.html', response.data)

    def test_get_organizer_my_events(self):
        """Test GET /organizer/my-events."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.get('/organizer/my-events')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'my_events.html', response.data)

    def test_get_organizer_my_events_unauthorized(self):
        """Test GET /organizer/my-events without organizer role."""
        with app.app_context():
            self.login_user('customer', 'StrongP@ss123')
            response = self.client.get('/organizer/my-events')
            self.assertEqual(response.status_code, 403)

    def test_get_organizer_create_event(self):
        """Test GET /organizer/create-event."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.get('/organizer/create-event')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'create_event.html', response.data)

    def test_post_organizer_create_event_success(self):
        """Test POST /organizer/create-event with valid data."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post('/organizer/create-event', data={
                'title': 'New Event',
                'description': 'Description',
                'category': 'music',
                'start_time': '2025-09-01T10:00',
                'end_time': '2025-09-01T12:00',
                'location': 'Location',
                'ticket_name': 'VIP',
                'price': 100,
                'ticket_quantity': 50
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(Event).count(), 2)

    def test_post_organizer_create_event_invalid(self):
        """Test POST /organizer/create-event with invalid end_time."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post('/organizer/create-event', data={
                'title': 'New Event',
                'description': 'Description',
                'category': 'music',
                'start_time': '2025-09-01T12:00',
                'end_time': '2025-09-01T10:00',
                'location': 'Location'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(db.session.query(Event).count(), 1)

    def test_get_event_detail(self):
        """Test GET /event/<event_id>."""
        with app.app_context():
            response = self.client.get(f'/event/{self.event.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'EventDetail.html', response.data)

    def test_get_event_detail_not_found(self):
        """Test GET /event/<event_id> with non-existing event."""
        with app.app_context():
            response = self.client.get('/event/999')
            self.assertEqual(response.status_code, 302)  # Redirects to events page
            self.assertIn(b'events', response.data)

    def test_get_organizer_event(self):
        """Test GET /organizer/event/<event_id>."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.get(f'/organizer/event/{self.event.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(self.event.title.encode(), response.data)

    def test_get_organizer_event_unauthorized(self):
        """Test GET /organizer/event/<event_id> without organizer role."""
        with app.app_context():
            self.login_user('customer', 'StrongP@ss123')
            response = self.client.get(f'/organizer/event/{self.event.id}')
            self.assertEqual(response.status_code, 403)

    def test_post_organizer_update_event_success(self):
        """Test POST /organizer/update-event/<event_id> with valid data."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post(f'/organizer/update-event/{self.event.id}', data={
                'title': 'Updated Event',
                'description': 'Updated Description',
                'category': 'music',
                'start_time': '2025-09-01T10:00',
                'end_time': '2025-09-01T12:00',
                'location': 'Updated Location'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertEqual(event.title, 'Updated Event')

    def test_post_organizer_update_event_invalid(self):
        """Test POST /organizer/update-event/<event_id> with invalid data."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post(f'/organizer/update-event/{self.event.id}', data={
                'title': 'Updated Event',
                'start_time': '2025-09-01T12:00',
                'end_time': '2025-09-01T10:00'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertEqual(event.title, 'Test Event')  # Title unchanged due to validation error

    def test_post_organizer_delete_event(self):
        """Test POST /organizer/delete-event/<event_id>."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post(f'/organizer/delete-event/{self.event.id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertFalse(event.is_active)

    def test_post_organizer_bulk_delete_events(self):
        """Test POST /organizer/bulk-delete-events."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post('/organizer/bulk-delete-events', data={
                'event_ids': [self.event.id]
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertFalse(event.is_active)

    def test_get_organizer_manage_staff(self):
        """Test GET /organizer/manage-staff."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.get('/organizer/manage-staff')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'manage_staff.html', response.data)

    def test_post_organizer_update_role(self):
        """Test POST /organizer/update-role/<user_id>."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post(f'/organizer/update-role/{self.customer.id}', data={
                'role': 'staff'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            user = db.session.query(User).get(self.customer.id)
            self.assertEqual(user.role, UserRole.staff)

    def test_post_organizer_assign_staff(self):
        """Test POST /organizer/assign-staff/<event_id>."""
        with app.app_context():
            self.login_user('organizer', 'StrongP@ss123')
            response = self.client.post(f'/organizer/assign-staff/{self.event.id}', data={
                'staff_ids': [self.staff.id]
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertIn(self.staff, event.staff)

    def test_get_auth_login(self):
        """Test GET /auth/login."""
        with app.app_context():
            response = self.client.get('/auth/login')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'login.html', response.data)

    def test_post_auth_login_success(self):
        """Test POST /auth/login with valid credentials."""
        with app.app_context():
            response = self.client.post('/auth/login', data={
                'username_or_email': 'customer',
                'password': 'StrongP@ss123',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(current_user.is_authenticated)
            self.assertEqual(current_user.username, 'customer')

    def test_post_auth_login_invalid(self):
        """Test POST /auth/login with invalid credentials."""
        with app.app_context():
            response = self.client.post('/auth/login', data={
                'username_or_email': 'customer',
                'password': 'WrongPassword',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(current_user.is_authenticated)

    def test_get_auth_register(self):
        """Test GET /auth/register."""
        with app.app_context():
            response = self.client.get('/auth/register')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'register.html', response.data)

    def test_post_auth_register_success(self):
        """Test POST /auth/register with valid data."""
        with app.app_context():
            response = self.client.post('/auth/register', data={
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'StrongP@ss123',
                'phone': '1234567890'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            user = db.session.query(User).filter_by(username='newuser').first()
            self.assertIsNotNone(user)
            self.assertTrue(current_user.is_authenticated)

    def test_post_auth_register_duplicate_email(self):
        """Test POST /auth/register with duplicate email."""
        with app.app_context():
            with db.session.begin_nested():
                response = self.client.post('/auth/register', data={
                    'username': 'newuser',
                    'email': 'customer@example.com',
                    'password': 'StrongP@ss123',
                    'phone': '1234567890'
                }, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(current_user.is_authenticated)
                self.assertEqual(db.session.query(User).filter_by(email='customer@example.com').count(), 1)

if __name__ == '__main__':
    unittest.main()