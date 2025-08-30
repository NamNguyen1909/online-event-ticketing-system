import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, request
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
import json

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
            db.drop_all()  # Ensure clean database before each test
            db.create_all()  # Create all tables
            self.client = self.app.test_client()

            # Create test users
            self.customer = self.create_user_and_commit(
                username='john_doe',
                email='jane@example.com',
                password='Password@123',
                role=UserRole.customer
            )
            self.organizer = self.create_user_and_commit(
                username='organizer',
                email='organizer@example.com',
                password='Password@123',
                role=UserRole.organizer
            )
            self.other_organizer = self.create_user_and_commit(
                username='other_organizer',
                email='other@example.com',
                password='Password@123',
                role=UserRole.organizer
            )

            # Create test events and ticket types
            self.event_10 =self.create_event_and_commit(self.organizer.id, title='Event 10')
            self.event_15 = self.create_event_and_commit(self.organizer.id, title='Conference')
            self.event_18 = self.create_event_and_commit(self.organizer.id, title='Event 18')
            self.event_20 = self.create_event_and_commit(self.organizer.id, title='Event 20')
            self.event_22 = self.create_event_and_commit(self.other_organizer.id, title='Event 22')  # Different organizer
            self.event_30 = self.create_event_and_commit(self.organizer.id, title='Event 30')
            self.ticket_type = self.create_ticket_type_and_commit(self.event_10.id)

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

    @patch('eventapp.dao.Event.query')
    def test_delete_event(self, mock_query):
        """Test delete_event with event_id 20."""
        mock_event = MagicMock(id=20, organizer_id=2, is_active=True)
        mock_query.get.return_value = mock_event
        delete_event(20, 2)
        self.assertFalse(mock_event.is_active)
        mock_query.get.assert_called_once_with(20)

    def test_validate_ticket_types(self):
        """Test validate_ticket_types with valid ticket types."""
        ticket_types = [
            {'name': 'VIP', 'price': 500000, 'total_quantity': 100},
            {'name': 'Regular', 'price': 200000, 'total_quantity': 300}
        ]
        result = validate_ticket_types(ticket_types)
        self.assertTrue(result)

    @patch('eventapp.dao.User.query')
    def test_update_user_role(self, mock_query):
        """Test update_user_role with user_id 7."""
        mock_user = MagicMock(id=7, role=UserRole.customer)
        mock_query.get.return_value = mock_user
        update_user_role(7, 'staff', 2)
        self.assertEqual(mock_user.role, UserRole.staff)
        self.assertEqual(mock_user.creator_id, 2)
        mock_query.get.assert_called_once_with(7)

    @patch('eventapp.dao.User.query')
    def test_update_user_role_invalid_role(self, mock_query):
        """Test update_user_role with invalid role."""
        mock_user = MagicMock(id=7, role=UserRole.customer)
        mock_query.get.return_value = mock_user
        with self.assertRaises(ValueError) as context:
            update_user_role(7, "invalid_role", None)
        self.assertEqual(str(context.exception), "Vai trò không hợp lệ")

class TestRoutesIntegration(EventHubTestCase):
    """Integration tests for routes in routes.py."""

    def test_post_organizer_delete_event(self):
        """Test POST /organizer/delete-event/18."""
        with app.app_context():
            self.login_user('organizer', 'Password@123')
            response = self.client.post(f'/organizer/delete-event/{self.event_18.id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            response_json = json.loads(response.data.decode('utf-8'))
            self.assertTrue(response_json['success'])
            self.assertEqual(response_json['message'], 'Xóa sự kiện thành công!')
            event = db.session.query(Event).get(self.event_18.id)
            self.assertFalse(event.is_active)

    def test_post_organizer_bulk_delete_events(self):
        """Test POST /organizer/bulk-delete-events with event_ids [25, 26, 27]."""
        with app.app_context():
            self.login_user('organizer', 'Password@123')
            response = self.client.post('/organizer/bulk-delete-events', json={
                'event_ids': [self.event_25.id, self.event_26.id, self.event_27.id]
            }, content_type='application/json', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            response_json = json.loads(response.data.decode('utf-8'))
            self.assertTrue(response_json['success'])
            self.assertEqual(response_json['message'], 'Xóa các sự kiện thành công!')
            for event_id in [self.event_25.id, self.event_26.id, self.event_27.id]:
                event = db.session.query(Event).get(event_id)
                self.assertFalse(event.is_active)

    def test_get_event_detail(self):
        """Test GET /event/30."""
        with app.app_context():
            self.login_user('organizer', 'Password@123')
            response = self.client.get(f'/event/{self.event_30.id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Event 30', response.data)

    def test_post_auth_login(self):
        """Test POST /auth/login with valid credentials."""
        with app.app_context():
            response = self.client.post('/auth/login', data={
                'username_or_email': 'jane@example.com',
                'password': 'Password@123',
                'remember_me': True
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(current_user.is_authenticated)
            self.assertEqual(current_user.email, 'jane@example.com')

    def test_post_auth_register(self):
        """Test POST /auth/register with valid data."""
        with app.app_context():
            response = self.client.post('/auth/register', data={
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'Password@123',
                'phone': '0123456789'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            user = db.session.query(User).filter_by(username='newuser').first()
            self.assertIsNotNone(user)
            self.assertTrue(current_user.is_authenticated)
            self.assertEqual(current_user.username, 'newuser')

if __name__ == '__main__':
    unittest.main()