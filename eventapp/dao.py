from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from eventapp.models import (
    User, Event, TicketType, Review, EventCategory, 
    EventTrendingLog, DiscountCode, Ticket, Payment, 
    UserNotification, CustomerGroup, PaymentMethod, Notification
)
from eventapp import db
from datetime import datetime, timedelta
from wtforms.validators import ValidationError
import uuid
import os
import hmac
import hashlib
from flask import request
import pytz

# User related functions
def check_user(username):
    """Kiểm tra người dùng theo username"""
    return User.query.filter(User.username == username).first()

def check_email(email):
    """Kiểm tra người dùng theo email"""
    return User.query.filter(User.email == email).first()

def get_user_by_username(username):
    """Lấy ID người dùng theo username"""
    user = User.query.filter(User.username == username).first()
    return user.id if user else None

def get_user_tickets(user_id):
    """Lấy vé của người dùng"""
    return Ticket.query.filter_by(user_id=user_id).all()

def get_user_events(user_id, page=1, per_page=10):
    """Lấy sự kiện của organizer với phân trang"""
    return Event.query.filter_by(organizer_id=user_id).order_by(Event.start_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

def get_user_payments(user_id):
    """Lấy thanh toán của người dùng"""
    return Payment.query.filter_by(user_id=user_id).all()

def get_user_notifications(user_id):
    """Lấy thông báo của người dùng"""
    return UserNotification.query.filter_by(user_id=user_id).order_by(UserNotification.created_at.desc()).all()

def get_user_customer_group(user):
    """Lấy nhóm khách hàng của người dùng"""
    try:
        return user.get_customer_group()
    except Exception as e:
        print(f"Error getting user group: {e}")
        return CustomerGroup.new

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

def get_all_events_revenue_stats():
    """Lấy thống kê doanh thu cho tất cả sự kiện"""
    events = db.session.query(Event).options(
        joinedload(Event.ticket_types)
    ).filter_by(is_active=True).all()

    stats = []
    total_revenue = 0
    for event in events:
        active_ticket_types = [tt for tt in event.ticket_types if tt.is_active]
        stat = calculate_event_stats(active_ticket_types, event.reviews.all())
        stats.append({
            'event_id': event.id,
            'title': event.title,
            'total_tickets': stat['total_tickets'],
            'sold_tickets': stat['sold_tickets'],
            'available_tickets': stat['available_tickets'],
            'revenue': stat['revenue'],
            'ticket_types': [{
                'name': tt.name,
                'price': float(tt.price),
                'total_quantity': tt.total_quantity,
                'sold_quantity': tt.sold_quantity
            } for tt in active_ticket_types]
        })
        total_revenue += stat['revenue']
    
    return stats, total_revenue

def search_events(page=1, per_page=12, category='', search='', start_date='', end_date='', location='', min_price=None, max_price=None):
    """Tìm kiếm và lọc sự kiện"""
    query = Event.query.filter_by(is_active=True)

    if category:
        query = query.filter(Event.category == category)

    if search:
        query = query.filter(Event.title.ilike(f'%{search}%'))

    if location:
        query = query.filter(Event.location.ilike(f'%{location}%'))

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
    """Lấy tiêu đề danh mục từ EventCategory enum"""
    category_value = category.value if hasattr(category, 'value') else category
    try:
        EventCategory(category_value)
        return category_value.title()
    except ValueError:
        print(f"Invalid category: {category_value}")
        return 'Unknown'

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

def validate_ticket_types(ticket_types, event_id=None):
    """Xác thực loại vé để tránh trùng lặp và kiểm tra ràng buộc"""
    names = set()
    for ticket in ticket_types:
        if ticket['name'] in names:
            raise ValidationError(f'Tên vé "{ticket["name"]}" bị trùng')
        if ticket['price'] < 0:
            raise ValidationError(f'Giá vé "{ticket["name"]}" phải không âm')
        if ticket['total_quantity'] < 1:
            raise ValidationError(f'Số lượng vé "{ticket["name"]}" phải ít nhất là 1')
        if event_id and ticket.get('id'):
            existing = TicketType.query.get(ticket['id'])
            if existing and existing.event_id == event_id and ticket['total_quantity'] < existing.sold_quantity:
                raise ValidationError(f'Không thể giảm số lượng vé dưới số vé đã bán cho "{ticket["name"]}"')
        names.add(ticket['name'])
    return True

def create_event(data, user_id):
    """Tạo sự kiện mới"""
    event = Event(
        organizer_id=user_id,
        title=data['title'],
        description=data['description'],
        category=EventCategory[data['category']],
        start_time=data['start_time'],
        end_time=data['end_time'],
        location=data['location'],
        is_active=True
    )
    db.session.add(event)
    db.session.flush()  # Get event.id

    # Create TicketType
    ticket_type = TicketType(
        event_id=event.id,
        name=data['ticket_name'],
        price=data['price'],
        total_quantity=data['ticket_quantity'],
        sold_quantity=0,
        is_active=True
    )
    db.session.add(ticket_type)

    # Upload poster if provided
    if data['poster']:
        event.upload_poster(data['poster'])

    db.session.commit()
    return event

def create_event_with_tickets(data, user_id):
    """Tạo sự kiện với nhiều loại vé"""
    validate_ticket_types(data['ticket_types'])
    event = Event(
        organizer_id=user_id,
        title=data['title'],
        description=data['description'],
        category=EventCategory[data['category']],
        start_time=data['start_time'],
        end_time=data['end_time'],
        location=data['location'],
        is_active=True
    )
    db.session.add(event)
    db.session.flush()
    for ticket_data in data['ticket_types']:
        ticket_type = TicketType(
            event_id=event.id,
            name=ticket_data['name'],
            price=ticket_data['price'],
            total_quantity=ticket_data['total_quantity'],
            sold_quantity=0,
            is_active=True
        )
        db.session.add(ticket_type)
    if data['poster']:
        event.upload_poster(data['poster'])
    db.session.commit()
    return event

def update_event(event_id, data, user_id):
    """Cập nhật sự kiện"""
    event = Event.query.get(event_id)
    if not event or event.organizer_id != user_id:
        raise ValueError('Event not found or not owned by user')

    # Update fields if provided
    if 'title' in data and data['title']:
        event.title = data['title']
    if 'description' in data and data['description']:
        event.description = data['description']
    if 'category' in data and data['category']:
        event.category = EventCategory[data['category']]
    if 'start_time' in data and data['start_time']:
        event.start_time = data['start_time']
    if 'end_time' in data and data['end_time']:
        event.end_time = data['end_time']
    if 'location' in data and data['location']:
        event.location = data['location']
    if 'poster' in data and data['poster']:
        event.upload_poster(data['poster'])

    # Update TicketType (assume first one)
    ticket_type = event.ticket_types.first()
    if ticket_type:
        if 'ticket_name' in data and data['ticket_name']:
            ticket_type.name = data['ticket_name']
        if 'price' in data and data['price'] is not None:
            ticket_type.price = data['price']
        if 'ticket_quantity' in data and data['ticket_quantity'] is not None:
            if data['ticket_quantity'] < ticket_type.sold_quantity:
                raise ValueError('Cannot reduce quantity below sold tickets')
            ticket_type.total_quantity = data['ticket_quantity']

    db.session.commit()
    return event

def update_event_with_tickets(event_id, data, user_id):
    """Cập nhật sự kiện với nhiều loại vé"""
    validate_ticket_types(data['ticket_types'], event_id)
    event = Event.query.get(event_id)
    if not event or event.organizer_id != user_id:
        raise ValueError('Sự kiện không tồn tại hoặc không thuộc quyền sở hữu')

    # Cập nhật các trường của sự kiện
    if 'title' in data and data['title']:
        event.title = data['title']
    if 'description' in data and data['description']:
        event.description = data['description']
    if 'category' in data and data['category']:
        event.category = EventCategory[data['category']]
    if 'start_time' in data and data['start_time']:
        event.start_time = data['start_time']
    if 'end_time' in data and data['end_time']:
        event.end_time = data['end_time']
    if 'location' in data and data['location']:
        event.location = data['location']
    if 'poster' in data and data['poster']:
        event.upload_poster(data['poster'])

    # Cập nhật loại vé
    existing_ticket_ids = {tt.id: tt for tt in event.ticket_types}
    new_ticket_ids = set()
    for ticket_data in data.get('ticket_types', []):
        ticket_id = ticket_data.get('id')
        if ticket_id and ticket_id in existing_ticket_ids:
            ticket = existing_ticket_ids[ticket_id]
            ticket.name = ticket_data['name']
            ticket.price = ticket_data['price']
            if ticket_data['total_quantity'] < ticket.sold_quantity:
                raise ValidationError(f'Không thể giảm số lượng vé dưới số vé đã bán cho {ticket.name}')
            ticket.total_quantity = ticket_data['total_quantity']
            new_ticket_ids.add(ticket_id)
        else:
            ticket = TicketType(
                event_id=event.id,
                name=ticket_data['name'],
                price=ticket_data['price'],
                total_quantity=ticket_data['total_quantity'],
                sold_quantity=0,
                is_active=True
            )
            db.session.add(ticket)

    # Xóa các loại vé không còn trong danh sách
    for ticket_id, ticket in existing_ticket_ids.items():
        if ticket_id not in new_ticket_ids:
            db.session.delete(ticket)

    db.session.commit()
    return event

def delete_event(event_id, user_id):
    """Xóa sự kiện (đặt is_active=False)"""
    event = Event.query.get(event_id)
    if not event or event.organizer_id != user_id:
        raise ValueError('Event not found or not owned by user')
    event.is_active = False
    db.session.commit()

def bulk_delete_events(event_ids, user_id):
    """Xóa nhiều sự kiện"""
    for event_id in event_ids:
        delete_event(event_id, user_id)

# Payment and ticket cleanup functions
def create_payment(user_id, amount, payment_method, status, transaction_id, discount_code=None):
    """Tạo bản ghi thanh toán"""
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
    """Cập nhật tổng chi tiêu của user và tính lại điểm trending cho event"""
    user = User.query.get(user_id)
    event = Event.query.get(event_id)
    if user and amount:
        user.total_spent = (user.total_spent or 0) + amount
    if event and event.trending_log:
        event.trending_log.calculate_score()
    db.session.commit()

def cleanup_unpaid_tickets(timeout_minutes=1):
    """Xóa các vé chưa thanh toán sau thời gian quy định"""
    expire_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    tickets = Ticket.query.filter(
        Ticket.is_paid == False,
        Ticket.purchase_date == None,
        Ticket.created_at < expire_time
    ).all()
    for ticket in tickets:
        db.session.delete(ticket)
    db.session.commit()

# VNPay functions
def vnpay_encode(value):
    from urllib.parse import quote_plus
    return quote_plus(str(value), safe='')

def create_payment_url_flask(amount, txn_ref):
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    host_url = request.host_url.rstrip('/')
    vnp_TmnCode = os.environ.get('VNPAY_TMN_CODE')
    vnp_HashSecret = os.environ.get('VNPAY_HASH_SECRET')
    vnp_Url = 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html'
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

def vnpay_redirect_flask():
    vnp_ResponseCode = request.args.get('vnp_ResponseCode')
    vnp_TxnRef = request.args.get('vnp_TxnRef')

    if vnp_ResponseCode is None:
        return "Thiếu tham số vnp_ResponseCode.", 400

    message = vnpay_response_message(vnp_ResponseCode)
    payment_success = vnp_ResponseCode == '00'

    payment = Payment.query.filter_by(transaction_id=vnp_TxnRef).first()

    if payment and payment_success:
        payment.status = True
        payment.paid_at = datetime.utcnow()
        tickets = Ticket.query.filter_by(payment_id=payment.id, user_id=payment.user_id, is_paid=False).all()

        if tickets:
            event_id = tickets[0].event_id
        for ticket in tickets:
            ticket.is_paid = True
            ticket.purchase_date = datetime.utcnow()
            ticket.generate_qr_code()
            if ticket.ticket_type:
                ticket.ticket_type.sold_quantity += 1
        if payment.discount_code:
            payment.discount_code.used_count += 1
        notif = Notification(
            event_id=event_id,
            title="Thanh toán thành công",
            message=f"Bạn đã thanh toán thành công đơn hàng {payment.transaction_id}.",
            notification_type="payment"
        )
        from eventapp.utils import send_ticket_email
        user = payment.user
        ticket_infos = []
        for ticket in tickets:
            ticket_infos.append({
                'event_title': ticket.event.title if ticket.event else '',
                'ticket_type': ticket.ticket_type.name if ticket.ticket_type else '',
                'qr_code_url': ticket.qr_code_url,
                'uuid': ticket.uuid
            })
        email_subject = f"Vé điện tử cho đơn hàng {payment.transaction_id}"
        html_body = f"""
        <div style='font-family:sans-serif;max-width:80%;margin:auto;background:#f9f9f9;border-radius:10px;padding:32px 24px 24px 24px;'>
            <div style='text-align:center;'>
                <h1 style='color:#2d8cf0;margin-bottom:8px;'>🎫 Vé điện tử của bạn</h1>
                <p style='font-size:18px;margin:0 0 12px 0;'>Cảm ơn bạn đã đặt vé tại <b>Event Hub</b>!</p>
                <p style='font-size:16px;margin:0 0 18px 0;'>Mã đơn hàng: <span style='color:#2d8cf0;font-weight:bold'>{payment.transaction_id}</span></p>
            </div>
            <table style='width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;'>
                <thead>
                    <tr style='background:#2d8cf0;color:#fff;'>
                        <th style='padding:10px 6px;'>Sự kiện</th>
                        <th style='padding:10px 6px;'>Loại vé</th>
                        <th style='padding:10px 6px;'>Mã QR</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([
                        f"<tr style='border-bottom:1px solid #eee;'>"
                        f"<td style='padding:10px 6px;font-weight:500;'>{t['event_title']}</td>"
                        f"<td style='padding:10px 6px;'>{t['ticket_type']}</td>"
                        f"<td style='padding:10px 6px;text-align:center;'><img src='{t['qr_code_url']}' width='120' style='border:2px solid #2d8cf0;border-radius:8px;background:#fff;padding:4px;'/><br><span style='font-size:12px;color:#888;'>Mã: {t['uuid']}</span></td>"
                        f"</tr>" for t in ticket_infos
                    ])}
                </tbody>
            </table>
            <div style='margin-top:24px;font-size:15px;color:#333;'>
                <p><b>Hướng dẫn sử dụng vé:</b></p>
                <ul style='margin:0 0 12px 18px;padding:0;'>
                    <li>Xuất trình mã QR này tại cổng check-in sự kiện.</li>
                    <li>Không chia sẻ mã QR cho người khác để tránh bị sử dụng mất quyền lợi.</li>
                    <li>Nếu có thắc mắc, liên hệ <a href='mailto:support@eventhub.vn'>support@eventhub.vn</a>.</li>
                </ul>
                <p style='color:#888;font-size:13px;margin-top:18px;'>Email này được gửi tự động. Vui lòng không trả lời lại email này.</p>
            </div>
        </div>
        """
        try:
            send_ticket_email(user.email, email_subject, html_body, tickets=ticket_infos)
        except Exception as e:
            print(f"[EMAIL ERROR] Không gửi được vé: {e}")
        update_user_and_event_after_payment(payment.user_id, event_id, payment.amount)
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

# Debug function
def get_all_events():
    """Lấy tất cả sự kiện (debug)"""
    return Event.query.all()