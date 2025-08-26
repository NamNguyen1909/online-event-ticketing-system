from eventapp import app, db, login_manager
from eventapp.models import PaymentMethod, Ticket,TicketType
from eventapp import dao
from flask import flash, jsonify, render_template, request, abort, session, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Blueprint, request, jsonify, redirect
from eventapp.dao import create_payment_url_flask, vnpay_redirect_flask,cleanup_unpaid_tickets

@app.route('/')
def index():
    """Trang chủ"""
    trending_events = dao.get_trending_events(limit=6)
    return render_template('index.html', events=trending_events)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Chi tiết sự kiện"""
    try:
        print(f"Searching for event with ID: {event_id}")
        
        # Load event với organizer
        event = dao.get_event_detail(event_id)
        
        if not event:
            print(f"Event with ID {event_id} not found or not active")
            abort(404)
        
        print(f"Found event: {event.title}, Category: {event.category}")
        
        # Lấy các ticket types đang hoạt động
        active_ticket_types = dao.get_active_ticket_types(event.id)
        print(f"Found {len(active_ticket_types)} active ticket types")
        
        # Lấy reviews
        main_reviews = dao.get_event_reviews(event.id)
        print(f"Found {len(main_reviews)} reviews")
        
        # Lấy tất cả reviews để tính rating
        all_reviews = dao.get_all_event_reviews(event.id)
        
        # Tính toán thống kê
        stats = dao.calculate_event_stats(active_ticket_types, all_reviews)
        print(f"Stats calculated: {stats}")
        
        # Kiểm tra quyền trả lời review
        can_reply = False
        if current_user.is_authenticated:
            can_reply = current_user.role.value in ['staff', 'organizer']
        
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

@app.route('/events')
def events():
    """Danh sách sự kiện với tìm kiếm và bộ lọc"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    location = request.args.get('location', '')
    price_min = request.args.get('price_min', type=float)
    price_max = request.args.get('price_max', type=float)
    quick_date = request.args.get('quick_date', '')
    free = request.args.get('free', '')

    # Xử lý quick_date (nếu muốn giữ các nút nhanh)
    from datetime import datetime, timedelta
    today = datetime.today()
    if quick_date == 'today':
        start_date = today.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif quick_date == 'tomorrow':
        tomorrow = today + timedelta(days=1)
        start_date = tomorrow.strftime('%Y-%m-%d')
        end_date = tomorrow.strftime('%Y-%m-%d')
    elif quick_date == 'weekend':
        # Tìm ngày thứ 7 và CN gần nhất
        saturday = today + timedelta((5 - today.weekday()) % 7)
        sunday = saturday + timedelta(days=1)
        start_date = saturday.strftime('%Y-%m-%d')
        end_date = sunday.strftime('%Y-%m-%d')
    elif quick_date == 'month':
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        # Tìm ngày cuối tháng
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        end_date = last_day.strftime('%Y-%m-%d')

    # Xử lý miễn phí
    if free:
        price_max = 0

    # Lấy danh sách thể loại cho dropdown
    from eventapp.models import EventCategory
    categories = list(EventCategory)

    events = dao.search_events(page, 12, category, search, start_date, end_date, location, price_min, price_max)
    category_title = None
    if category:
        from eventapp.dao import get_category_title
        category_title = get_category_title(category)
    return render_template('customer/EventList.html', events=events, categories=categories, category_title=category_title)

@app.route('/trending')
def trending():
    """Hiển thị sự kiện trending"""
    trending_events = dao.get_trending_events()
    return render_template('customer/EventList.html', 
                         events={'items': trending_events}, 
                         category_title='Sự Kiện Trending')

@app.route('/category/<category>')
def category(category):
    """Hiển thị sự kiện theo danh mục"""
    events = dao.get_events_by_category(category)
    if events is None:
        abort(404)

    category_title = dao.get_category_title(category)
    from eventapp.models import EventCategory
    categories = list(EventCategory)

    return render_template('customer/EventList.html', 
                  events=events, 
                  category=category,
                  category_title=category_title,
                  categories=categories)

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
    from eventapp.models import Ticket
    recent_tickets = Ticket.query.filter_by(user_id=current_user.id, is_paid=True).order_by(Ticket.purchase_date.desc()).limit(5).all()
    return render_template('customer/Profile.html', user=current_user, recent_tickets=recent_tickets)

# Route chỉnh sửa thông tin hồ sơ
from flask import request, redirect, flash, url_for

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = current_user
    message = None
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        avatar_file = request.files.get('avatar')

        from eventapp.models import User
        # Kiểm tra trùng username
        if username and username != user.username:
            if User.query.filter(User.username==username, User.id!=user.id).first():
                message = 'Tên đăng nhập đã tồn tại!'
            else:
                user.username = username
        # Kiểm tra trùng email
        if email and email != user.email:
            if User.query.filter(User.email==email, User.id!=user.id).first():
                message = 'Email đã tồn tại!'
            else:
                user.email = email
        if phone:
            user.phone = phone
        if avatar_file and avatar_file.filename:
            try:
                user.upload_avatar(avatar_file)
            except Exception as e:
                message = f'Lỗi cập nhật ảnh đại diện: {str(e)}'

        # Đổi mật khẩu nếu có nhập
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if old_password or new_password or confirm_password:
            if not old_password or not new_password or not confirm_password:
                message = 'Vui lòng nhập đầy đủ thông tin đổi mật khẩu!'
            elif not check_password_hash(user.password_hash, old_password):
                message = 'Mật khẩu hiện tại không đúng!'
            elif new_password != confirm_password:
                message = 'Mật khẩu mới không khớp!'
            elif len(new_password) < 6:
                message = 'Mật khẩu mới phải từ 6 ký tự trở lên!'
            else:
                user.password_hash = generate_password_hash(new_password)

        from eventapp import db
        try:
            db.session.commit()
            if not message:
                message = 'Cập nhật hồ sơ thành công!'
        except Exception as e:
            db.session.rollback()
            message = f'Lỗi cập nhật hồ sơ: {str(e)}'
        return render_template('customer/EditProfile.html', user=user, message=message)
    # GET: render form chỉnh sửa riêng
    return render_template('customer/EditProfile.html', user=user, message=message)

# Route đổi mật khẩu
@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    message = None
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not check_password_hash(current_user.password_hash, old_password):
            message = 'Mật khẩu cũ không đúng!'
        elif new_password != confirm_password:
            message = 'Mật khẩu mới không khớp!'
        elif len(new_password) < 6:
            message = 'Mật khẩu mới phải từ 6 ký tự trở lên!'
        else:
            current_user.password_hash = generate_password_hash(new_password)
            try:
                db.session.commit()
                message = 'Đổi mật khẩu thành công!'
            except Exception as e:
                db.session.rollback()
                message = f'Lỗi đổi mật khẩu: {str(e)}'
    return render_template('customer/ChangePassword.html', user=current_user, message=message)

@app.route('/my-tickets')
@login_required
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id, is_paid=True).order_by(Ticket.purchase_date.desc()).all()
    return render_template('customer/MyTickets.html', tickets=tickets)

@app.route('/my-events')
@login_required
def my_events():
    events = dao.get_user_events(current_user.id)
    return render_template('my_events.html', events=events)

@app.route('/orders')
@login_required
def orders():
    payments = dao.get_user_payments(current_user.id)
    return render_template('orders.html', payments=payments)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@app.route('/notifications')
@login_required
def notifications():
    notifications = dao.get_user_notifications(current_user.id)
    return render_template('notifications.html', notifications=notifications)

@app.route('/debug/events')
def debug_events():
    """Debug route để xem có events nào trong database"""
    events = dao.get_all_events()
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
        
        # Load event
        event = dao.get_event_for_booking(event_id)
        
        if not event:
            print(f"[BOOK_TICKET] Event {event_id} not found or not active")
            flash('Sự kiện không tồn tại hoặc đã bị xóa.', 'error')
            return redirect(url_for('events'))
        
        print(f"[BOOK_TICKET] Found event: {event.title}")
        
        # Load ticket types
        all_ticket_types = dao.get_all_ticket_types_for_event(event_id)
        print(f"[BOOK_TICKET] Event has {len(all_ticket_types)} ticket types")
        
        # Lấy các ticket types khả dụng
        available_ticket_types = dao.get_available_ticket_types(all_ticket_types)
        print(f"[BOOK_TICKET] Available ticket types: {len(available_ticket_types)}")
        
        if not available_ticket_types:
            print(f"[BOOK_TICKET] No available tickets for event {event_id}")
            flash('Sự kiện này hiện tại đã hết vé.', 'warning')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Lấy nhóm khách hàng
        user_group = dao.get_user_customer_group(current_user)
        print(f"[BOOK_TICKET] User group: {user_group}")

        # Lấy mã giảm giá
        available_discounts = dao.get_user_discount_codes(user_group)
        print(f"[BOOK_TICKET] Found {len(available_discounts)} discount codes")

        
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
    """Xử lý đặt vé (AJAX)"""
    cleanup_unpaid_tickets() #lazy cleanup ticket chưa thanh toán
    
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        tickets_data = data.get('tickets')
        
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
        is_valid, error_message = dao.validate_ticket_availability(data.get('tickets'))
        if not is_valid:
            return jsonify({'success': False, 'message': error_message})



        # Nếu chọn VNPay
        if payment_method == 'vnpay':
            # Tạo transaction_id duy nhất
            import uuid
            transaction_id = f"VNPAY_{uuid.uuid4().hex[:12]}"
            # Tạo bản ghi Payment (status=False)
            payment = dao.create_payment(
                user_id=current_user.id,
                amount=data['total_amount'],
                payment_method=payment_method,
                status=False,
                transaction_id=transaction_id,
                discount_code=data.get('discount_code')
            )
            db.session.commit()


            # Tạo các vé với is_paid=False
            for ticket_info in tickets_data:
                ticket_type = TicketType.query.get(ticket_info['ticket_type_id'])
                event_id = ticket_type.event_id if ticket_type else None
                for _ in range(ticket_info['quantity']):
                    ticket = Ticket(
                        user_id=current_user.id,
                        event_id=event_id,
                        ticket_type_id=ticket_info['ticket_type_id'],
                        is_paid=False,
                        purchase_date=None,
                        payment_id=payment.id
                    )
                    db.session.add(ticket)
                    # Cập nhật sold_quantity tạm thời nếu muốn (hoặc chỉ tăng khi thanh toán thành công)
            db.session.commit()



            # Tạo URL thanh toán VNPay
            payment_url = dao.create_payment_url_flask(data['total_amount'], txn_ref=transaction_id)
            return jsonify({'success': True, 'payment_url': payment_url})
        

        # Nếu là phương thức khác (COD, chuyển khoản, ...)
        # ...xử lý như cũ...
        return jsonify({'success': True, 'message': 'Đặt vé thành công!'})
        
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
    

@app.route('/vnpay/create_payment', methods=['POST'])
def vnpay_create_payment():
    data = request.get_json()
    amount = data.get('amount')
    txn_ref = data.get('txn_ref')
    payment_url = create_payment_url_flask(amount, txn_ref)
    return jsonify({'payment_url': payment_url})

@app.route('/vnpay/redirect')
def vnpay_redirect():
    return vnpay_redirect_flask()

# API/job xóa vé chưa thanh toán
from datetime import datetime, timedelta

@app.route('/tickets/cleanup', methods=['POST'])
def cleanup():
    cleanup_unpaid_tickets()
    return jsonify({'cleanup_unpaid_tickets called'})