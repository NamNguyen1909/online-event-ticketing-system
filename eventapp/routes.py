from eventapp import app, db,login_manager
from eventapp.models import DiscountCode, Event, PaymentMethod, TicketType, Review, User, EventCategory, Ticket, Payment, UserNotification, EventTrendingLog
from flask import flash, jsonify, render_template, request, abort, session
from sqlalchemy.orm import joinedload
from datetime import datetime
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, flash
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
        
        # Kiểm tra quyền trả lời review dựa trên Flask-Login's current_user
        can_reply = False
        if current_user.is_authenticated:
            # Cho phép reply nếu user là staff hoặc organizer
            can_reply = current_user.role.value in ['staff', 'organizer']
        
        # KHÔNG override current_user trong template context
        return render_template('customer/EventDetail.html', 
                             event=event, 
                             ticket_types=active_ticket_types,
                             reviews=main_reviews,
                             stats=stats,
                             can_reply=can_reply)
                             
    except Exception as e:
        print(f"Error in event_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        abort(500)

# Code cũ
# @app.route('/events')
# def events():
#     """Danh sách sự kiện"""
#     page = request.args.get('page', 1, type=int)
#     category = request.args.get('category', '')
#     search = request.args.get('search', '')
    
#     query = Event.query.filter_by(is_active=True)
    
#     if category:
#         query = query.filter_by(category=category)
    
#     if search:
#         query = query.filter(Event.title.contains(search))
    
#     events = query.order_by(Event.start_time.desc()).paginate(
#         page=page, per_page=12, error_out=False
#     )
    
#     return render_template('customer/EventList.html', events=events)

@app.route('/events')
def events():
    """Danh sách sự kiện với tìm kiếm và bộ lọc"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    query = Event.query.filter_by(is_active=True)

    if category:
        query = query.filter(Event.category == category)

    if search:
        query = query.filter(Event.title.ilike(f'%{search}%'))

    if start_date:
        try:
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Event.start_time >= start_dt)
        except:
            pass

    if end_date:
        try:
            from datetime import datetime
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Event.end_time <= end_dt)
        except:
            pass

    # Lọc theo giá vé thấp nhất của event
    if min_price is not None:
        query = query.join(Event.ticket_types).filter(TicketType.price >= min_price)
    if max_price is not None:
        query = query.join(Event.ticket_types).filter(TicketType.price <= max_price)

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
                      events=events, 
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

@app.route('/booking/event/<int:event_id>')
@login_required
def book_ticket(event_id):
    """Trang đặt vé cho sự kiện"""
    try:
        print(f"[BOOK_TICKET] User {current_user.username} accessing event {event_id}")
        
        # Load event thông thường (không dùng joinedload cho ticket_types)
        event = Event.query.filter_by(id=event_id, is_active=True).first()
        
        if not event:
            print(f"[BOOK_TICKET] Event {event_id} not found or not active")
            flash('Sự kiện không tồn tại hoặc đã bị xóa.', 'error')
            return redirect(url_for('events'))
        
        print(f"[BOOK_TICKET] Found event: {event.title}")
        
        # Load ticket types riêng biệt
        all_ticket_types = TicketType.query.filter_by(event_id=event_id).all()
        print(f"[BOOK_TICKET] Event has {len(all_ticket_types)} ticket types")
        
        # Lấy các ticket types đang hoạt động và còn vé
        available_ticket_types = [tt for tt in all_ticket_types 
                                if tt.is_active and tt.sold_quantity < tt.total_quantity]
        
        print(f"[BOOK_TICKET] Available ticket types: {len(available_ticket_types)}")
        
        if not available_ticket_types:
            print(f"[BOOK_TICKET] No available tickets for event {event_id}")
            flash('Sự kiện này hiện tại đã hết vé.', 'warning')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Kiểm tra method get_user_group có tồn tại không
        try:
            user_group = current_user.get_customer_group()  
            print(f"[BOOK_TICKET] User group: {user_group}")
        except Exception as e:
            print(f"[BOOK_TICKET] Error getting user group: {e}")
            from eventapp.models import CustomerGroup
            user_group = CustomerGroup.new  # Default group

        # Sửa query discount codes:
        try:
            current_time = datetime.now()
            available_discounts = DiscountCode.query.filter(
                DiscountCode.user_group == user_group,
                DiscountCode.is_active == True,
                DiscountCode.valid_from <= current_time,
                DiscountCode.valid_to >= current_time,
                DiscountCode.used_count < DiscountCode.max_uses
            ).all()
            print(f"[BOOK_TICKET] Found {len(available_discounts)} discount codes")
        except Exception as e:
            print(f"[BOOK_TICKET] Error loading discount codes: {e}")
            available_discounts = []
        
        print(f"[BOOK_TICKET] Rendering BookTicket.html")
        return render_template('customer/BookTicket.html', 
                             event=event,
                             ticket_types=available_ticket_types,
                             discount_codes=available_discounts,
                             payment_methods=PaymentMethod)
                             
    except Exception as e:
        print(f"[BOOK_TICKET] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Đã xảy ra lỗi khi tải trang đặt vé.', 'error')
        return redirect(url_for('index'))

@app.route('/booking/process', methods=['POST'])
@login_required
def process_booking():
    """Xử lý thông tin đặt vé"""
    try:
        data = request.get_json()
        
        # Log thông tin booking để kiểm tra
        print("=== BOOKING INFORMATION ===")
        print(f"User: {current_user.username} (ID: {current_user.id})")
        print(f"Event ID: {data.get('event_id')}")
        print(f"Tickets: {data.get('tickets')}")
        print(f"Payment Method: {data.get('payment_method')}")
        print(f"Discount Code: {data.get('discount_code', 'None')}")
        print(f"Subtotal: {data.get('subtotal')}")
        print(f"Discount Amount: {data.get('discount_amount')}")
        print(f"Total Amount: {data.get('total_amount')}")
        print("========================")
        
        # Validation
        if not data.get('tickets') or len(data.get('tickets')) == 0:
            return jsonify({'success': False, 'message': 'Vui lòng chọn ít nhất một loại vé.'})
        
        total_tickets = sum(ticket['quantity'] for ticket in data.get('tickets'))
        if total_tickets == 0:
            return jsonify({'success': False, 'message': 'Vui lòng chọn ít nhất một vé.'})
        
        # Kiểm tra tồn kho
        for ticket in data.get('tickets'):
            ticket_type = TicketType.query.get(ticket['ticket_type_id'])
            if not ticket_type or ticket['quantity'] > (ticket_type.total_quantity - ticket_type.sold_quantity):
                return jsonify({'success': False, 'message': f'Không đủ vé loại {ticket_type.name if ticket_type else "Unknown"}'})
        
        return jsonify({'success': True, 'message': 'Đặt vé thành công! (Demo mode)'})
        
    except Exception as e:
        print(f"Error in process_booking: {str(e)}")
        return jsonify({'success': False, 'message': 'Đã xảy ra lỗi khi xử lý đặt vé.'})
    
@app.route('/debug/session')
def debug_session():
    """Debug session info"""
    import json
    from flask import session
    
    session_info = {
        'current_user_authenticated': current_user.is_authenticated,
        'current_user_id': current_user.id if current_user.is_authenticated else None,
        'current_user_username': current_user.username if current_user.is_authenticated else None,
        'session_keys': list(session.keys()),
        'session_permanent': session.permanent,
    }
    
    return f"<pre>{json.dumps(session_info, indent=2)}</pre>"

# Thêm vào routes.py
@app.route('/debug/full-session')
def debug_full_session():
    """Debug session info chi tiết"""
    import json
    from flask import session, request
    
    session_info = {
        'request_headers': dict(request.headers),
        'request_cookies': dict(request.cookies),
        'current_user_authenticated': current_user.is_authenticated,
        'current_user_id': current_user.id if current_user.is_authenticated else None,
        'current_user_username': current_user.username if current_user.is_authenticated else None,
        'session_items': dict(session),
        'session_permanent': session.permanent,
        'session_modified': session.modified,
        'app_secret_key_set': bool(app.config.get('SECRET_KEY')),
        'login_manager_user_loader': login_manager.user_loader is not None,
    }
    
    return f"<pre>{json.dumps(session_info, indent=2, default=str)}</pre>"

@app.route('/test-auth')
def test_auth():
    """Test authentication status"""
    if current_user.is_authenticated:
        return f"<h2>Đã đăng nhập</h2><p>User: {current_user.username}</p><p>ID: {current_user.id}</p>"
    else:
        return f"<h2>Chưa đăng nhập</h2><p><a href='{url_for('auth.login')}'>Đăng nhập</a></p>"