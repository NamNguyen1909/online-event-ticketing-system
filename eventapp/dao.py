from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from eventapp.models import (
    User, Event, TicketType, Review, EventCategory, 
    EventTrendingLog, DiscountCode, Ticket, Payment, 
    UserNotification, CustomerGroup
)
from eventapp import db
from datetime import datetime

def check_user(username):
    return User.query.filter(User.username == username).first()

def check_email(email):
    return User.query.filter(User.email == email).first()

def get_user_by_username(username):
    user = User.query.filter(User.username == username).first()
    return user.id if user else None

# Event related functions
def get_featured_events(limit=3):
    """Lấy các sự kiện nổi bật"""
    return Event.query.filter_by(is_active=True).limit(limit).all()

def get_event_detail(event_id):
    """Lấy chi tiết sự kiện"""
    return db.session.query(Event).options(
        joinedload(Event.organizer)
    ).filter_by(id=event_id, is_active=True).first()

def get_active_ticket_types(event_id):
    """Lấy các loại vé đang hoạt động"""
    return TicketType.query.filter_by(
        event_id=event_id, 
        is_active=True
    ).all()

def get_event_reviews(event_id, limit=5):
    """Lấy reviews của sự kiện"""
    return db.session.query(Review).options(
        joinedload(Review.user)
    ).filter_by(
        event_id=event_id,
        parent_review_id=None
    ).order_by(Review.created_at.desc()).limit(limit).all()

def get_all_event_reviews(event_id):
    """Lấy tất cả reviews của sự kiện để tính rating"""
    return Review.query.filter_by(event_id=event_id, parent_review_id=None).all()

def calculate_event_stats(active_ticket_types, all_reviews):
    """Tính toán thống kê sự kiện"""
    total_tickets = sum(tt.total_quantity for tt in active_ticket_types) if active_ticket_types else 0
    sold_tickets = sum(tt.sold_quantity for tt in active_ticket_types) if active_ticket_types else 0
    available_tickets = total_tickets - sold_tickets
    revenue = sum(tt.price * tt.sold_quantity for tt in active_ticket_types) if active_ticket_types else 0
    average_rating = sum(r.rating for r in all_reviews) / len(all_reviews) if all_reviews else 0
    
    return {
        'total_tickets': total_tickets,
        'sold_tickets': sold_tickets,
        'available_tickets': available_tickets,
        'revenue': revenue,
        'average_rating': round(average_rating, 1) if average_rating else 0,
        'review_count': len(all_reviews)
    }

def search_events(page=1, per_page=12, category='', search='', start_date='', end_date='', min_price=None, max_price=None):
    """Tìm kiếm và lọc sự kiện"""
    query = Event.query.filter_by(is_active=True)

    if category:
        query = query.filter(Event.category == category)

    if search:
        query = query.filter(Event.title.ilike(f'%{search}%'))

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Event.start_time >= start_dt)
        except:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Event.end_time <= end_dt)
        except:
            pass

    if min_price is not None:
        query = query.join(Event.ticket_types).filter(TicketType.price >= min_price)
    if max_price is not None:
        query = query.join(Event.ticket_types).filter(TicketType.price <= max_price)

    return query.order_by(Event.start_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

def get_trending_events(limit=10):
    """Lấy sự kiện trending"""
    try:
        return Event.query.join(EventTrendingLog).order_by(EventTrendingLog.trending_score.desc()).limit(limit).all()
    except Exception as e:
        print(f"Error in get_trending_events: {e}")
        return Event.query.filter_by(is_active=True).order_by(Event.start_time.desc()).limit(limit).all()

def get_events_by_category(category):
    """Lấy sự kiện theo danh mục"""
    try:
        category_enum = EventCategory[category.lower()]
        return Event.query.filter_by(category=category_enum, is_active=True).all()
    except KeyError:
        return None

def get_category_title(category):
    """Lấy tiêu đề danh mục"""
    category_titles = {
        'music': 'Âm Nhạc',
        'sports': 'Thể Thao', 
        'seminar': 'Hội Thảo',
        'conference': 'Hội Nghị',
        'festival': 'Lễ Hội',
        'workshop': 'Workshop',
        'party': 'Tiệc Party',
        'competition': 'Cuộc Thi',
        'other': 'Khác'
    }
    return category_titles.get(category.lower(), category.title())

# User related functions
def get_user_tickets(user_id):
    """Lấy vé của người dùng"""
    return Ticket.query.filter_by(user_id=user_id).all()

def get_user_events(user_id):
    """Lấy sự kiện của organizer"""
    return Event.query.filter_by(organizer_id=user_id).all()

def get_user_payments(user_id):
    """Lấy thanh toán của người dùng"""
    return Payment.query.filter_by(user_id=user_id).all()

def get_user_notifications(user_id):
    """Lấy thông báo của người dùng"""
    return UserNotification.query.filter_by(user_id=user_id).order_by(UserNotification.created_at.desc()).all()

def get_all_events():
    """Lấy tất cả sự kiện (debug)"""
    return Event.query.all()

# Booking related functions
def get_event_for_booking(event_id):
    """Lấy sự kiện cho đặt vé"""
    return Event.query.filter_by(id=event_id, is_active=True).first()

def get_all_ticket_types_for_event(event_id):
    """Lấy tất cả loại vé của sự kiện"""
    return TicketType.query.filter_by(event_id=event_id).all()

def get_available_ticket_types(all_ticket_types):
    """Lọc loại vé còn khả dụng"""
    return [tt for tt in all_ticket_types 
            if tt.is_active and tt.sold_quantity < tt.total_quantity]

def get_user_discount_codes(user_group):
    """Lấy mã giảm giá khả dụng cho người dùng"""
    try:
        current_time = datetime.now()
        return DiscountCode.query.filter(
            DiscountCode.user_group == user_group,
            DiscountCode.is_active == True,
            DiscountCode.valid_from <= current_time,
            DiscountCode.valid_to >= current_time,
            DiscountCode.used_count < DiscountCode.max_uses
        ).all()
    except Exception as e:
        print(f"Error loading discount codes: {e}")
        return []

def validate_ticket_availability(tickets_data):
    """Kiểm tra tồn kho vé"""
    for ticket in tickets_data:
        ticket_type = TicketType.query.get(ticket['ticket_type_id'])
        if not ticket_type or ticket['quantity'] > (ticket_type.total_quantity - ticket_type.sold_quantity):
            return False, f'Không đủ vé loại {ticket_type.name if ticket_type else "Unknown"}'
    return True, None

def get_user_customer_group(user):
    """Lấy nhóm khách hàng của user"""
    try:
        return user.get_customer_group()
    except Exception as e:
        print(f"Error getting user group: {e}")
        return CustomerGroup.new