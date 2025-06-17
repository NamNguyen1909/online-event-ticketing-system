from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import CheckConstraint, Index
import enum
import uuid
import math

db = SQLAlchemy()

# User roles enum
class UserRole(enum.Enum):
    admin = 'admin'
    organizer = 'organizer'
    attendee = 'attendee'

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True, nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.attendee, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)

    total_spent = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organized_events = relationship('Event', back_populates='organizer', lazy='dynamic')
    tickets = relationship('Ticket', back_populates='user', lazy='dynamic')
    payments = relationship('Payment', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

class EventCategory(enum.Enum):
    music = 'music'
    sports = 'sports'
    seminar = 'seminar'
    conference = 'conference'
    festival = 'festival'
    workshop = 'workshop'
    party = 'party'
    competition = 'competition'
    other = 'other'

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), index=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.Enum(EventCategory), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    total_tickets = db.Column(db.Integer, nullable=False)
    ticket_price = db.Column(db.Numeric(9, 2), nullable=False)
    sold_tickets = db.Column(db.Integer, default=0, nullable=False)

    poster_url = db.Column(db.String(512), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organizer = relationship('User', back_populates='organized_events')
    tickets = relationship('Ticket', back_populates='event', lazy='dynamic')
    trending_log = relationship('EventTrendingLog', uselist=False, back_populates='event')

    __table_args__ = (
        CheckConstraint('start_time < end_time', name='start_time_before_end_time'),
        Index('ix_event_start_end', 'start_time', 'end_time'),
        Index('ix_event_organizer', 'organizer_id'),
    )

    def __repr__(self):
        return f'<Event {self.title}>'

class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    qr_code_url = db.Column(db.String(512), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_paid = db.Column(db.Boolean, default=False, nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=True)

    is_checked_in = db.Column(db.Boolean, default=False, nullable=False)
    check_in_date = db.Column(db.DateTime, nullable=True)

    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)

    # Relationships
    user = relationship('User', back_populates='tickets')
    event = relationship('Event', back_populates='tickets')
    payment = relationship('Payment', back_populates='tickets')

    __table_args__ = (
        Index('ix_ticket_user_event', 'user_id', 'event_id'),
        Index('ix_ticket_qr_code', 'qr_code_url'),
    )

    def __repr__(self):
        return f'<Ticket user={self.user_id} event={self.event_id}>'

    def mark_as_paid(self, paid_at):
        self.is_paid = True
        self.purchase_date = paid_at

    def check_in(self):
        if not self.is_checked_in:
            self.is_checked_in = True
            self.check_in_date = datetime.utcnow()

class PaymentMethod(enum.Enum):
    momo = 'momo'
    vnpay = 'vnpay'

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    status = db.Column(db.Boolean, default=False, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    transaction_id = db.Column(db.String(255), unique=True, nullable=False)

    # Relationships
    user = relationship('User', back_populates='payments')
    tickets = relationship('Ticket', back_populates='payment', lazy='dynamic')

    __table_args__ = (
        Index('ix_payment_user_status', 'user_id', 'status'),
        Index('ix_payment_transaction_id', 'transaction_id'),
    )

    def __repr__(self):
        return f'<Payment {self.transaction_id}>'

    def save(self):
        if self.status and not self.paid_at:
            self.paid_at = datetime.utcnow()
        # Mark tickets as paid
        for ticket in self.tickets:
            if not ticket.is_paid:
                ticket.mark_as_paid(self.paid_at)

class EventTrendingLog(db.Model):
    __tablename__ = 'event_trending_logs'

    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), primary_key=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    total_revenue = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    trending_score = db.Column(db.Numeric(10, 4), default=0, nullable=False)
    interest_score = db.Column(db.Numeric(10, 4), default=0, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = relationship('Event', back_populates='trending_log')

    __table_args__ = (
        Index('ix_trending_event_last_updated', 'event_id', 'last_updated'),
    )

    def calculate_score(self):
        today = datetime.utcnow().date()
        sold_tickets = self.event.sold_tickets
        total_tickets = self.event.total_tickets
        # Since Review model is removed, set review_count to 0
        review_count = 0
        sales_start_date = self.event.created_at.date() if self.event.created_at else today

        sold_ratio = sold_tickets / total_tickets if total_tickets else 0
        days_since_sales_start = (today - sales_start_date).days or 1
        velocity = sold_tickets / days_since_sales_start
        views = self.view_count

        trending_score = (
            (sold_ratio * 0.5) +
            (velocity * 0.3) +
            (math.log(views + 1) * 0.2)
        )
        self.trending_score = round(trending_score, 4)

        interest_score = (
            (self.trending_score * 0.5) +
            (sold_tickets * 0.3) +
            (review_count * 0.2)
        )
        self.interest_score = round(interest_score, 4)

        db.session.commit()

    def __repr__(self):
        return f'<EventTrendingLog event_id={self.event_id}>'
