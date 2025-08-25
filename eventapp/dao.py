from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from eventapp.models import (
    User, Event, TicketType, Review, EventCategory, 
    EventTrendingLog, DiscountCode, Ticket, Payment, 
    UserNotification, CustomerGroup,Notification,PaymentMethod
)
from eventapp import db
from datetime import datetime, timedelta

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
    

# ======================================== VNPay ========================================
import os
import hmac
import hashlib
from flask import request, jsonify, redirect, current_app
import pytz

def vnpay_encode(value):
    from urllib.parse import quote_plus
    return quote_plus(str(value), safe='')

def create_payment_url_flask(amount, txn_ref):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    host_url=request.host_url.rstrip('/')
    vnp_TmnCode = os.environ.get('VNPAY_TMN_CODE')
    vnp_HashSecret = os.environ.get('VNPAY_HASH_SECRET')
    vnp_Url = 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
    backend_base_url = host_url
    vnp_ReturnUrl = f'{host_url}/vnpay/redirect'

    order_id = txn_ref or datetime.now(tz).strftime('%H%M%S')
    create_date = datetime.now(tz).strftime('%Y%m%d%H%M%S')
    ip_address = request.remote_addr

    input_data = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": vnp_TmnCode,
        "vnp_Amount": str(int(float(amount)) * 100),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": order_id,
        "vnp_OrderInfo": "Thanh toan don hang",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": vnp_ReturnUrl,
        "vnp_IpAddr": ip_address,
        "vnp_CreateDate": create_date
    }

    query_string = '&'.join(
        f"{k}={vnpay_encode(v)}"
        for k, v in sorted(input_data.items())
        if v
    )
    hash_data = '&'.join(
        f"{k}={vnpay_encode(v)}"
        for k, v in sorted(input_data.items())
        if v and k != "vnp_SecureHash"
    )

    secure_hash = hmac.new(
        bytes(vnp_HashSecret, 'utf-8'),
        bytes(hash_data, 'utf-8'),
        hashlib.sha512
    ).hexdigest()
    payment_url = f"{vnp_Url}?{query_string}&vnp_SecureHash={secure_hash}"
    return payment_url

def vnpay_response_message(code):
    mapping = {
        "00": "Giao dịch thành công.",
        "07": "Trừ tiền thành công. Giao dịch bị nghi ngờ (liên quan tới lừa đảo, giao dịch bất thường).",
        "09": "Thẻ/Tài khoản chưa đăng ký InternetBanking.",
        "10": "Xác thực thông tin thẻ/tài khoản không đúng quá 3 lần.",
        "11": "Hết hạn chờ thanh toán. Vui lòng thực hiện lại giao dịch.",
        "12": "Thẻ/Tài khoản bị khóa.",
        "13": "Sai mật khẩu xác thực giao dịch (OTP).",
        "24": "Khách hàng hủy giao dịch.",
        "51": "Tài khoản không đủ số dư.",
        "65": "Tài khoản vượt quá hạn mức giao dịch trong ngày.",
        "75": "Ngân hàng thanh toán đang bảo trì.",
        "79": "Sai mật khẩu thanh toán quá số lần quy định.",
        "99": "Lỗi khác hoặc không xác định.",
    }
    return mapping.get(code, "Lỗi không xác định.")

from flask import request, redirect, render_template_string
import urllib.parse

def vnpay_redirect_flask():
    vnp_ResponseCode = request.args.get('vnp_ResponseCode')
    vnp_TxnRef = request.args.get('vnp_TxnRef')

    if vnp_ResponseCode is None:
        return "Thiếu tham số vnp_ResponseCode.", 400

    message = vnpay_response_message(vnp_ResponseCode)
    payment_success = vnp_ResponseCode == '00'

    

    payment = Payment.query.filter_by(transaction_id=vnp_TxnRef).first()
    if payment:
        event_id=payment.event_id

    if payment and payment_success:
        payment.status = True
        payment.paid_at = datetime.utcnow()
        # Cập nhật các ticket liên quan
        tickets = Ticket.query.filter_by(payment_id=payment.id, user_id=payment.user_id, is_paid=False).all()
        for ticket in tickets:
            ticket.is_paid = True
            ticket.purchase_date = datetime.utcnow()
            # Cập nhật sold_quantity
            if ticket.ticket_type:
                ticket.ticket_type.sold_quantity += 1
        # Cập nhật DiscountCode nếu có
        if payment.discount_code:
            payment.discount_code.used_count += 1
        # Tạo notification
        notif = Notification(
            event_id=event_id,
            title="Thanh toán thành công",
            message=f"Bạn đã thanh toán thành công đơn hàng {payment.transaction_id}.",
            notification_type="payment"
        )
        # Cập nhật thông tin người dùng và sự kiện sau khi thanh toán
        update_user_and_event_after_payment(payment.user_id, event_id, float(payment.amount))
        
        db.session.add(notif)
        db.session.flush()
        notif.send_to_user(payment.user)
        db.session.commit()
    elif payment and not payment_success:
        notif = Notification(
            event_id=event_id,
            title="Thanh toán thất bại",
            message=f"Thanh toán đơn hàng {payment.transaction_id} không thành công.",
            notification_type="payment"
        )
        db.session.add(notif)
        db.session.flush()
        notif.send_to_user(payment.user)

    # Redirect về trang nội bộ
    redirect_url = '/my-tickets'
    if payment_success:
        redirect_url += '?payment_result=success'
    else:
        redirect_url += '?payment_result=failed'

    return render_template_string(f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="utf-8"/>
            <title>Kết quả thanh toán</title>
            <script>
                setTimeout(function() {{
                    window.location.href = "{redirect_url}";
                }}, 3000);
            </script>
        </head>
        <body style="font-family:sans-serif;text-align:center;padding-top:100px;">
            <h2>{'🎉 Thanh toán thành công!' if payment_success else '😔 Thanh toán thất bại!'}</h2>
            <p>{message}</p>
            <p>Bạn sẽ được chuyển hướng sau 3 giây...</p>
            <a href="{redirect_url}">Quay lại</a>
        </body>
        </html>
    """)


def create_payment(user_id, amount, payment_method, status, transaction_id, discount_code=None):
    """
    Tạo một đối tượng Payment mới.
    """
    payment = Payment(
        user_id=user_id,
        amount=amount,
        payment_method=PaymentMethod(payment_method),
        status=status,
        transaction_id=transaction_id
    )
    if discount_code:
        dc = DiscountCode.query.filter_by(code=discount_code).first()
        if dc:
            payment.discount_code = dc
    db.session.add(payment)
    return payment

def update_user_and_event_after_payment(user_id, event_id, amount):
    """
    Cập nhật tổng chi tiêu của user và tính lại điểm trending cho event sau khi thanh toán thành công.
    """
    user = User.query.get(user_id)
    event = Event.query.get(event_id)
    if user and amount:
        user.total_spent = (user.total_spent or 0) + amount
    if event and event.trending_log:
        event.trending_log.calculate_score()
    db.session.commit()

def cleanup_unpaid_tickets(timeout_minutes=1):
    expire_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    tickets = Ticket.query.filter(
        Ticket.is_paid == False,
        Ticket.purchase_date == None,
        Ticket.created_at < expire_time
    ).all()
    for ticket in tickets:
        db.session.delete(ticket)
    db.session.commit()

