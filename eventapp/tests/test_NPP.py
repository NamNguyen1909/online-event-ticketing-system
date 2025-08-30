import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_testing import TestCase
from flask_login import login_user, current_user
from eventapp import app, db
from eventapp.models import User, UserRole, Event, TicketType, EventCategory, Ticket
from eventapp.dao import (
    check_user, check_email, get_event_detail, get_user_events,
    create_event_with_tickets, update_event_with_tickets, delete_event,
    bulk_delete_events, validate_ticket_types, update_user_role
)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import uuid
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

    def create_user_and_commit(self, username, email, password, role=UserRole.customer, creator_id=None):
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
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
            return user

    def create_event_and_commit(self, organizer_id, title='Test Event'):
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
                is_active=True
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

    def setUp(self):
        """Set up test database and environment."""
        with app.app_context():
            db.create_all()  # Ensure all tables (including tickets) are created
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

            # Create test event and ticket type
            self.event = self.create_event_and_commit(self.organizer.id)
            self.ticket_type = self.create_ticket_type_and_commit(self.event.id)

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

    @patch('eventapp.dao.User.query')
    def test_check_user_success(self, mock_query):
        """Test check_user with existing username."""
        mock_user = MagicMock(id=1)
        mock_query.filter_by.return_value.first.return_value = mock_user
        result = check_user('customer')
        self.assertEqual(result, mock_user)
        mock_query.filter_by.assert_called_once_with(username='customer')

    @patch('eventapp.dao.User.query')
    def test_check_email_success(self, mock_query):
        """Test check_email with existing email."""
        mock_user = MagicMock(id=1)
        mock_query.filter_by.return_value.first.return_value = mock_user
        result = check_email('customer@example.com')
        self.assertEqual(result, mock_user)
        mock_query.filter_by.assert_called_once_with(email='customer@example.com')

    @patch('eventapp.dao.db.session.query')
    def test_get_event_detail_success(self, mock_query):
        """Test get_event_detail with valid event ID."""
        mock_event = MagicMock(id=1)
        mock_query.return_value.options.return_value.filter_by.return_value.first.return_value = mock_event
        result = get_event_detail(self.event.id)
        self.assertEqual(result, mock_event)
        mock_query.return_value.options.return_value.filter_by.assert_called_once_with(id=self.event.id, is_active=True)

    @patch('eventapp.dao.Event.query')
    def test_get_user_events_success(self, mock_query):
        """Test get_user_events with existing events."""
        mock_paginate = MagicMock(items=[MagicMock(id=1, title='Test Event')], total=1)
        mock_query.filter_by.return_value.order_by.return_value.paginate.return_value = mock_paginate
        result = get_user_events(self.organizer.id)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, 'Test Event')
        mock_query.filter_by.assert_called_once_with(organizer_id=self.organizer.id)

    @patch('eventapp.dao.db.session')
    def test_create_event_with_tickets_success(self, mock_db_session):
        """Test create_event_with_tickets with valid data."""
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        event = create_event_with_tickets(
            organizer_id=self.organizer.id,
            ticket_types=ticket_types,
            title='New Event',
            description='Description',
            category=EventCategory.music,
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=2),
            location='Location'
        )
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called_once()
        self.assertIsNotNone(event)
        self.assertEqual(event.title, 'New Event')

    @patch('eventapp.dao.Event.query')
    def test_update_event_with_tickets_success(self, mock_query):
        """Test update_event_with_tickets with valid data."""
        mock_event = MagicMock(organizer_id=self.organizer.id)
        mock_query.get.return_value = mock_event
        data = {
            'title': 'Updated Event',
            'description': 'Updated Description',
            'category': 'music',
            'start_time': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'end_time': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'location': 'Updated Location'
        }
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        result = update_event_with_tickets(self.event.id, data, ticket_types, self.organizer.id)
        self.assertEqual(result, mock_event)
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_delete_event_success(self, mock_query):
        """Test delete_event with valid event."""
        mock_event = MagicMock(organizer_id=self.organizer.id, is_active=True)
        mock_query.get.return_value = mock_event
        delete_event(self.event.id, self.organizer.id)
        self.assertFalse(mock_event.is_active)
        mock_query.get.assert_called_once_with(self.event.id)

    @patch('eventapp.dao.Event.query')
    def test_bulk_delete_events_success(self, mock_query):
        """Test bulk_delete_events with valid events."""
        mock_event = MagicMock(organizer_id=self.organizer.id, is_active=True)
        mock_query.filter_by.return_value.all.return_value = [mock_event]
        result = bulk_delete_events([self.event.id], self.organizer.id)
        self.assertTrue(result)
        self.assertFalse(mock_event.is_active)
        mock_query.filter_by.assert_called_once_with(organizer_id=self.organizer.id)

    def test_validate_ticket_types_success(self):
        """Test validate_ticket_types with valid ticket types."""
        ticket_types = [{'name': 'VIP', 'price': 100, 'total_quantity': 50}]
        validate_ticket_types(ticket_types)
        # No exception means success

    @patch('eventapp.dao.User.query')
    def test_update_user_role_success(self, mock_query):
        """Test update_user_role to staff role."""
        mock_user = MagicMock(role=UserRole.customer)
        mock_query.get.return_value = mock_user
        update_user_role(self.customer.id, 'staff', self.organizer.id)
        self.assertEqual(mock_user.role, UserRole.staff)
        self.assertEqual(mock_user.creator_id, self.organizer.id)
        mock_query.get.assert_called_once_with(self.customer.id)

class TestRoutesIntegration(EventHubTestCase):
    """Integration tests for routes in routes.py."""

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
            response = self.client.post('/organizer/bulk-delete-events', json={
                'event_ids': [self.event.id]
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            event = db.session.query(Event).get(self.event.id)
            self.assertFalse(event.is_active)

    def test_get_event_detail(self):
        """Test GET /event/<event_id>."""
        with app.app_context():
            response = self.client.get(f'/event/{self.event.id}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(self.event.title.encode(), response.data)

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

if __name__ == '__main__':
    unittest.main()