from eventapp import app, db
from eventapp.models import Event, TicketType, Review, User, EventCategory, Ticket, Payment, UserNotification, EventTrendingLog
from flask import render_template, request, abort, session
from sqlalchemy.orm import joinedload
from datetime import datetime
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user

@app.route('/')
def index():
    """Trang chủ"""
    featured_events = Event.query.filter_by(is_active=True).limit(3).all()
    return render_template('index.html', events=featured_events)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Chi tiết sự kiện"""
    try:
        print(f"Searching for event with ID: {event_id}")
        
        # Load event với chỉ organizer
        event = db.session.query(Event).options(
            joinedload(Event.organizer)
        ).filter_by(id=event_id, is_active=True).first()
        
        if not event:
            print(f"Event with ID {event_id} not found or not active")
            abort(404)
        
        print(f"Found event: {event.title}, Category: {event.category}")
        
        # Lấy các ticket types đang hoạt động
        active_ticket_types = TicketType.query.filter_by(
            event_id=event.id, 
            is_active=True
        ).all()
        
        print(f"Found {len(active_ticket_types)} active ticket types")
        
        # Lấy reviews với user
        main_reviews = db.session.query(Review).options(
            joinedload(Review.user)
        ).filter_by(
            event_id=event.id,
            parent_review_id=None
        ).order_by(Review.created_at.desc()).limit(5).all()
        
        print(f"Found {len(main_reviews)} reviews")
        
        # Tính toán thống kê
        total_tickets = sum(tt.total_quantity for tt in active_ticket_types) if active_ticket_types else 0
        sold_tickets = sum(tt.sold_quantity for tt in active_ticket_types) if active_ticket_types else 0
        available_tickets = total_tickets - sold_tickets
        
        # Tính revenue từ ticket_types
        revenue = sum(tt.price * tt.sold_quantity for tt in active_ticket_types) if active_ticket_types else 0
        
        # Tính average rating
        all_reviews = Review.query.filter_by(event_id=event.id, parent_review_id=None).all()
        average_rating = sum(r.rating for r in all_reviews) / len(all_reviews) if all_reviews else 0
        
        stats = {
            'total_tickets': total_tickets,
            'sold_tickets': sold_tickets,
            'available_tickets': available_tickets,
            'revenue': revenue,
            'average_rating': round(average_rating, 1) if average_rating else 0,
            'review_count': len(all_reviews)
        }
        
        print(f"Stats calculated: {stats}")
        print(f"Rendering template with event category: {event.category.value}")
        
        # Kiểm tra quyền trả lời review
        current_user_obj = None
        can_reply = False
        
        if 'user_id' in session:
            current_user_obj = User.query.get(session['user_id'])
            if current_user_obj:
                # Cho phép reply nếu user là staff hoặc organizer
                can_reply = current_user_obj.role in ['staff', 'organizer']
        
        return render_template('customer/EventDetail.html', 
                             event=event, 
                             ticket_types=active_ticket_types,
                             reviews=main_reviews,
                             stats=stats,
                             current_user=current_user_obj,
                             can_reply=can_reply)
                             
    except Exception as e:
        print(f"Error in event_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        abort(500)

@app.route('/events')
def events():
    """Danh sách sự kiện"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    query = Event.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    
    if search:
        query = query.filter(Event.title.contains(search))
    
    events = query.order_by(Event.start_time.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('customer/EventList.html', events=events)

@app.route('/trending')
def trending():
    """Hiển thị sự kiện trending"""
    try:
        trending_events = Event.query.join(EventTrendingLog).order_by(EventTrendingLog.trending_score.desc()).limit(10).all()
        return render_template('customer/EventList.html', events={'items': trending_events}, category_title='Sự Kiện Trending')
    except Exception as e:
        print(f"Error in trending: {e}")
        events = Event.query.filter_by(is_active=True).order_by(Event.start_time.desc()).limit(10).all()
        return render_template('customer/EventList.html', events={'items': events}, category_title='Sự Kiện Phổ Biến')

@app.route('/category/<category>')
def category(category):
    """Hiển thị sự kiện theo danh mục"""
    try:
        category_enum = EventCategory[category.lower()]
        events = Event.query.filter_by(category=category_enum, is_active=True).all()
        
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
        
        category_title = category_titles.get(category.lower(), category.title())
        
        return render_template('customer/EventList.html', 
                             events={'items': events}, 
                             category=category,
                             category_title=category_title)
    except KeyError:
        abort(404)

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/policy')
def policy():
    return render_template('policy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/my-tickets')
@login_required
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/my-events')
@login_required
def my_events():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    return render_template('my_events.html', events=events)

@app.route('/orders')
@login_required
def orders():
    payments = Payment.query.filter_by(user_id=current_user.id).all()
    return render_template('orders.html', payments=payments)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@app.route('/notifications')
@login_required
def notifications():
    notifications = UserNotification.query.filter_by(user_id=current_user.id).order_by(UserNotification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/debug/events')
def debug_events():
    """Debug route để xem có events nào trong database"""
    events = Event.query.all()
    return f"Có {len(events)} events trong database: {[e.id for e in events]}"


# Routes cho Staff
@app.route('/staff/scan')
@login_required
def staff_scan():
    if current_user.role.value != 'staff':
        abort(403)
    return render_template('staff/scan.html')

# Routes cho Organizer
@app.route('/organizer/dashboard')
@login_required
def organizer_dashboard():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/dashboard.html')

@app.route('/organizer/create-event')
@login_required
def create_event():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/create_event.html')

@app.route('/organizer/analytics')
@login_required
def event_analytics():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/analytics.html')

@app.route('/organizer/staff-management')
@login_required
def manage_staff():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/staff_management.html')

@app.route('/organizer/add-staff')
@login_required
def add_staff():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/add_staff.html')

@app.route('/organizer/staff-permissions')
@login_required
def staff_permissions():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/permissions.html')

@app.route('/organizer/revenue-reports')
@login_required
def revenue_reports():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/revenue_reports.html')

# Routes cho Admin
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role.value != 'admin':
        abort(403)
    return render_template('admin/dashboard.html')

@app.route('/admin/users')
@login_required
def user_management():
    if current_user.role.value != 'admin':
        abort(403)
    return render_template('admin/user_management.html')

@app.route('/admin/events/moderation')
@login_required
def event_moderation():
    if current_user.role.value != 'admin':
        abort(403)
    return render_template('admin/event_moderation.html')

@app.route('/admin/settings')
@login_required
def system_settings():
    if current_user.role.value != 'admin':
        abort(403)
    return render_template('admin/settings.html')