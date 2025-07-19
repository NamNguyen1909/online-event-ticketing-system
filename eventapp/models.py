from datetime import datetime, timedelta
from sqlalchemy.orm import relationship
from sqlalchemy import CheckConstraint, Index
import enum
import uuid
import math

from eventapp import db

# User roles enum
class UserRole(enum.Enum):
    admin = 'admin'
    organizer = 'organizer'
    staff='staff'
    customer='customer'

# Customer groups enum
class CustomerGroup(enum.Enum):
    new = 'new'
    regular = 'regular'
    vip = 'vip'
    super_vip = 'super_vip'

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True, nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.customer, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)

    total_spent = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organized_events = relationship('Event', back_populates='organizer', lazy='dynamic')
    tickets = relationship('Ticket', back_populates='user', lazy='dynamic')
    payments = relationship('Payment', back_populates='user', lazy='dynamic')
    reviews = relationship('Review', back_populates='user', lazy='dynamic')
    user_notifications = relationship('UserNotification', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def get_customer_group(self):
        """Determine user group based on total_spent and account age"""
        now = datetime.utcnow()
        if (now - self.created_at) <= timedelta(days=7):
            return CustomerGroup.new
        elif self.total_spent < 500000:  # < 500k
            return CustomerGroup.regular
        elif self.total_spent < 2000000:  # 500k - 2M
            return CustomerGroup.vip
        else:  # >= 2M
            return CustomerGroup.super_vip

    def get_unread_notifications(self):
        """Get all unread notifications for this user"""
        return self.user_notifications.filter_by(is_read=False)

    def get_notifications(self, limit=None):
        """Get all notifications for this user, optionally limited"""
        query = self.user_notifications.order_by(UserNotification.created_at.desc())
        if limit:
            query = query.limit(limit)
        return query

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
    location = db.Column(db.String(500), nullable=False)

    # Remove single ticket fields - will be replaced by TicketType model
    # total_tickets = db.Column(db.Integer, nullable=False)
    # ticket_price = db.Column(db.Numeric(9, 2), nullable=False)
    # sold_tickets = db.Column(db.Integer, default=0, nullable=False)

    poster_url = db.Column(db.String(512), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organizer = relationship('User', back_populates='organized_events')
    tickets = relationship('Ticket', back_populates='event', lazy='dynamic')
    ticket_types = relationship('TicketType', back_populates='event', lazy='dynamic')
    reviews = relationship('Review', back_populates='event', lazy='dynamic')
    trending_log = relationship('EventTrendingLog', uselist=False, back_populates='event')

    __table_args__ = (
        CheckConstraint('start_time < end_time', name='start_time_before_end_time'),
        Index('ix_event_start_end', 'start_time', 'end_time'),
        Index('ix_event_organizer', 'organizer_id'),
    )

    def __repr__(self):
        return f'<Event {self.title}>'

    @property
    def total_tickets(self):
        """Calculate total tickets from all ticket types"""
        return sum(tt.total_quantity for tt in self.ticket_types)

    @property
    def sold_tickets(self):
        """Calculate total sold tickets from all ticket types"""
        return sum(tt.sold_quantity for tt in self.ticket_types)

    @property
    def available_tickets(self):
        """Calculate total available tickets"""
        return self.total_tickets - self.sold_tickets

    @property
    def is_sold_out(self):
        """Check if all ticket types are sold out"""
        ticket_types_list = list(self.ticket_types)
        if not ticket_types_list:
            return False  # No ticket types means not sold out
        return all(tt.is_sold_out for tt in ticket_types_list)

    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = [r for r in self.reviews if r.parent_review_id is None]  # Only main reviews, not replies
        if not reviews:
            return 0
        return sum(r.rating for r in reviews) / len(reviews)

    @property
    def revenue(self):
        """Calculate total revenue from sold tickets"""
        return sum(tt.sold_quantity * tt.price for tt in self.ticket_types)

    @property 
    def is_upcoming(self):
        """Check if event is upcoming"""
        return self.start_time > datetime.utcnow()

    @property
    def is_ongoing(self):
        """Check if event is currently ongoing"""
        now = datetime.utcnow()
        return self.start_time <= now <= self.end_time

    @property
    def is_past(self):
        """Check if event has ended"""
        return self.end_time < datetime.utcnow()

    def get_active_ticket_types(self):
        """Get only active ticket types"""
        return [tt for tt in self.ticket_types if tt.is_active]

class TicketType(db.Model):
    __tablename__ = 'ticket_types'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # VIP, Regular, Student, etc.
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(9, 2), nullable=False)
    total_quantity = db.Column(db.Integer, nullable=False)
    sold_quantity = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event = relationship('Event', back_populates='ticket_types')
    tickets = relationship('Ticket', back_populates='ticket_type', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('sold_quantity <= total_quantity', name='sold_not_exceed_total'),
        CheckConstraint('price >= 0', name='price_non_negative'),
        Index('ix_ticket_type_event', 'event_id'),
    )

    def __repr__(self):
        return f'<TicketType {self.name} for Event {self.event_id}>'

    @property
    def available_quantity(self):
        return self.total_quantity - self.sold_quantity

    @property
    def is_sold_out(self):
        return self.sold_quantity >= self.total_quantity

class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    ticket_type_id = db.Column(db.Integer, db.ForeignKey('ticket_types.id'), nullable=False)
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
    ticket_type = relationship('TicketType', back_populates='tickets')
    payment = relationship('Payment', back_populates='tickets')

    __table_args__ = (
        Index('ix_ticket_user_event', 'user_id', 'event_id'),
        Index('ix_ticket_type', 'ticket_type_id'),
        Index('ix_ticket_qr_code', 'qr_code_url'),
        # Note: MySQL doesn't support subqueries in CHECK constraints
        # Data integrity will be enforced at application level
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

    @property
    def price(self):
        """Get ticket price from ticket type"""
        return self.ticket_type.price if self.ticket_type else 0

    def validate_ticket_availability(self):
        """Check if ticket type still has available quantity"""
        if self.ticket_type and self.ticket_type.is_sold_out:
            raise ValueError(f"Ticket type {self.ticket_type.name} is sold out")

class PaymentMethod(enum.Enum):
    momo = 'momo'
    vnpay = 'vnpay'

class DiscountCode(db.Model):
    __tablename__ = 'discount_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, index=True, nullable=False)
    discount_percentage = db.Column(db.Numeric(5, 2), nullable=False)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_to = db.Column(db.DateTime, nullable=False)
    user_group = db.Column(db.Enum(CustomerGroup), default=CustomerGroup.regular, nullable=False)
    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = relationship('Payment', back_populates='discount_code', lazy='dynamic')

    __table_args__ = (
        CheckConstraint('valid_from <= valid_to', name='valid_from_before_valid_to'),
        CheckConstraint('discount_percentage >= 0 AND discount_percentage <= 100', name='valid_discount_percentage'),
        Index('ix_discount_code_active', 'code', 'is_active'),
    )

    def __repr__(self):
        return f'<DiscountCode {self.code}>'

    def is_valid(self):
        """Check if discount code is currently valid"""
        now = datetime.utcnow()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_to and
            (self.max_uses is None or self.used_count < self.max_uses)
        )

    def can_be_used_by_user(self, user):
        """Check if this discount code can be used by the specific user"""
        if not self.is_valid():
            return False
        
        user_group = self.get_user_group(user)
        return user_group == self.user_group

    def get_user_group(self, user):
        """Determine user group based on total_spent - should match User.get_customer_group()"""
        now = datetime.utcnow()
        if (now - user.created_at) <= timedelta(days=7):
            return CustomerGroup.new
        elif user.total_spent < 500000:
            return CustomerGroup.regular
        elif user.total_spent < 2000000:
            return CustomerGroup.vip
        else:
            return CustomerGroup.super_vip

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    status = db.Column(db.Boolean, default=False, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    transaction_id = db.Column(db.String(255), unique=True, nullable=False)
    discount_code_id = db.Column(db.Integer, db.ForeignKey('discount_codes.id'), nullable=True)

    # Relationships
    user = relationship('User', back_populates='payments')
    discount_code = relationship('DiscountCode', back_populates='payments')
    tickets = relationship('Ticket', back_populates='payment', lazy='dynamic')

    __table_args__ = (
        Index('ix_payment_user_status', 'user_id', 'status'),
        Index('ix_payment_transaction_id', 'transaction_id'),
    )

    def __repr__(self):
        return f'<Payment {self.transaction_id}>'

    def save(self):
        """Save payment and mark associated tickets as paid"""
        if self.status and not self.paid_at:
            self.paid_at = datetime.utcnow()
        
        # Save payment first
        db.session.add(self)
        db.session.flush()  # Ensure payment ID is available
        
        # Mark tickets as paid
        for ticket in self.tickets:
            if not ticket.is_paid:
                ticket.mark_as_paid(self.paid_at)
        
        # Update ticket type sold quantities
        for ticket in self.tickets:
            if ticket.ticket_type and not ticket.is_paid:
                ticket.ticket_type.sold_quantity += 1
        
        db.session.commit()

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
        # Calculate total sold tickets from all ticket types
        sold_tickets = sum(tt.sold_quantity for tt in self.event.ticket_types)
        total_tickets = sum(tt.total_quantity for tt in self.event.ticket_types)
        # Get review count from reviews relationship
        review_count = self.event.reviews.count() if self.event.reviews else 0
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

# Review system
class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text, nullable=True)
    parent_review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=True)  # For replies

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event = relationship('Event', back_populates='reviews')
    user = relationship('User', back_populates='reviews')
    parent_review = relationship('Review', remote_side=[id], backref='replies')

    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='valid_rating'),
        Index('ix_review_event_user', 'event_id', 'user_id'),
        Index('ix_review_parent', 'parent_review_id'),
    )

    def __repr__(self):
        return f'<Review {self.rating} stars for Event {self.event_id}>'

    @property
    def is_reply(self):
        """Check if this review is a reply to another review"""
        return self.parent_review_id is not None

    @property
    def is_from_organizer(self):
        """Check if this review/reply is from the event organizer"""
        if self.is_reply:
            return self.user_id == self.event.organizer_id
        return False

# Notification system - Fixed to match Django approach
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # reminder, update, etc.

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship('Event')
    user_notifications = relationship('UserNotification', back_populates='notification', lazy='dynamic')

    __table_args__ = (
        Index('ix_notification_type', 'notification_type'),
        Index('ix_notification_event', 'event_id'),
    )

    def __repr__(self):
        return f'<Notification {self.title}>'

    def send_to_user(self, user, send_email=False):
        """Send this notification to a specific user"""
        user_notification = UserNotification(
            user_id=user.id,
            notification_id=self.id,
            is_email_sent=send_email
        )
        db.session.add(user_notification)
        return user_notification

    def send_to_users(self, users, send_email=False):
        """Send this notification to multiple users"""
        user_notifications = []
        for user in users:
            user_notification = UserNotification(
                user_id=user.id,
                notification_id=self.id,
                is_email_sent=send_email
            )
            user_notifications.append(user_notification)
            db.session.add(user_notification)
        return user_notifications

    def send_to_event_participants(self, send_email=False):
        """Send notification to all users who have tickets for this event"""
        if not self.event:
            return []
        
        # Get unique users who have tickets for this event
        users = db.session.query(User).join(Ticket).filter(
            Ticket.event_id == self.event_id
        ).distinct().all()
        
        return self.send_to_users(users, send_email)

# Many-to-many relationship between User and Notification with read status
class UserNotification(db.Model):
    __tablename__ = 'user_notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_id = db.Column(db.Integer, db.ForeignKey('notifications.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_email_sent = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='user_notifications')
    notification = relationship('Notification', back_populates='user_notifications')

    __table_args__ = (
        Index('ix_user_notification_user_read', 'user_id', 'is_read'),
        Index('ix_user_notification_user_notif', 'user_id', 'notification_id'),
        # Ensure each user gets each notification only once
        db.UniqueConstraint('user_id', 'notification_id', name='unique_user_notification'),
    )

    def __repr__(self):
        return f'<UserNotification User:{self.user_id} Notification:{self.notification_id}>'

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

# Language support structure (for future i18n integration)
class Translation(db.Model):
    __tablename__ = 'translations'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), index=True, nullable=False)
    language = db.Column(db.String(5), nullable=False)  # en, vi
    value = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_translation_key_lang', 'key', 'language'),
    )

    def __repr__(self):
        return f'<Translation {self.key}:{self.language}>'
