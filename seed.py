from faker import Faker
from datetime import datetime, timedelta
import random
from decimal import Decimal
import uuid
import os
from flask import Flask

from eventapp import db
from eventapp.models import (
    User, Event, TicketType, Ticket, Payment, Review, 
    Notification, UserNotification, DiscountCode, EventTrendingLog,
    UserRole, EventCategory, CustomerGroup, PaymentMethod
)
from werkzeug.security import generate_password_hash

# Khởi tạo Faker với locale tiếng Việt
fake = Faker(['vi_VN', 'en_US'])

def generate_phone_number():
    """Tạo số điện thoại Việt Nam với độ dài phù hợp (10-11 số)"""
    prefixes = ['090', '091', '093', '094', '096', '097', '098', '099', 
                '070', '076', '077', '078', '079', '081', '082', '083', 
                '084', '085', '086', '087', '088', '089']
    prefix = random.choice(prefixes)
    suffix = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix}{suffix}"

def create_users(num_users=50):
    """Tạo người dùng giả"""
    users = []
    
    # Đảm bảo email duy nhất
    used_emails = set()

    # Tạo admin
    admin_email = 'admin@example.com'
    admin = User(
        username='admin',
        email=admin_email,
        password_hash=generate_password_hash('admin123'),
        role=UserRole.admin,
        phone=generate_phone_number(),
        total_spent=Decimal('0'),
        is_active=True
    )
    users.append(admin)
    used_emails.add(admin_email)

    # Tạo organizer
    for i in range(5):
        org_email = f'organizer{i+1}@example.com'
        while org_email in used_emails:
            org_email = f'organizer{i+1}_{random.randint(1,9999)}@example.com'
        organizer = User(
            username=f'organizer_{i+1}',
            email=org_email,

            password_hash=generate_password_hash('password123'),
            role=UserRole.organizer,
            phone=generate_phone_number(),
            total_spent=Decimal(random.uniform(100000, 5000000)),
            is_active=True,
            created_at=fake.date_time_between(start_date='-2y', end_date='now')
        )
        users.append(organizer)
        
        used_emails.add(org_email)

    # Tạo staff, gán creator_id là organizer ngẫu nhiên
    organizers = [u for u in users if u.role == UserRole.organizer]
    for i in range(3):
        staff_email = f'staff{i+1}@example.com'
        while staff_email in used_emails:
            staff_email = f'staff{i+1}_{random.randint(1,9999)}@example.com'
        staff = User(
            username=f'staff_{i+1}',
            email=staff_email,

            password_hash=generate_password_hash('password123'),
            role=UserRole.staff,
            phone=generate_phone_number(),
            total_spent=Decimal('0'),
            is_active=True,
            creator_id=random.choice(organizers).id if organizers else None
        )
        users.append(staff)

        used_emails.add(staff_email)

    # Tạo customers
    for i in range(num_users - 9):
        # Sinh email unique
        email = fake.email()
        tries = 0
        while email in used_emails:
            email = fake.email()
            tries += 1
            if tries > 10:
                email = f'customer{i}_{random.randint(1,99999)}@example.com'
        used_emails.add(email)

        customer = User(
            username=fake.user_name() + str(i),
            email=email,
            password_hash=generate_password_hash('password123'),
            role=UserRole.customer,
            phone=generate_phone_number(),
            total_spent=Decimal(random.uniform(0, 3000000)),
            is_active=random.choice([True, True, True, False]),  # 75% active
            created_at=fake.date_time_between(start_date='-1y', end_date='now')
        )
        users.append(customer)


    db.session.add_all(users)
    db.session.commit()
    return users

def create_events(users, num_events=30):
    """Tạo sự kiện giả"""
    events = []
    organizers = [u for u in users if u.role == UserRole.organizer]
    staff_users = [u for u in users if u.role == UserRole.staff]

    for i in range(num_events):
        start_time = fake.date_time_between(start_date='-1m', end_date='+3m')
        end_time = start_time + timedelta(hours=random.randint(3, 12))

        event = Event(
            organizer_id=random.choice(organizers).id,
            title=fake.sentence(nb_words=4).replace('.', ''),
            description=fake.text(max_nb_chars=500),
            category=random.choice(list(EventCategory)),
            start_time=start_time,
            end_time=end_time,
            location=fake.address(),
            is_active=random.choice([True, True, True, False]),  # 75% active
            created_at=fake.date_time_between(start_date='-2m', end_date='now')
        )
        # Gán staff cho event (1-3 staff ngẫu nhiên)
        if staff_users:
            num_staff = random.randint(1, min(3, len(staff_users)))
            selected_staff = random.sample(staff_users, num_staff)
            for staff in selected_staff:
                event.staff.append(staff)
        events.append(event)

    db.session.add_all(events)
    db.session.commit()
    return events

def create_ticket_types(events):
    """Tạo loại vé cho các sự kiện"""
    ticket_types = []
    ticket_type_names = ['VIP', 'Regular', 'Student', 'Early Bird', 'Group']
    
    for event in events:
        # Mỗi event có 2-4 loại vé
        num_types = random.randint(2, 4)
        selected_types = random.sample(ticket_type_names, num_types)
        
        for i, type_name in enumerate(selected_types):
            base_price = random.randint(50000, 2000000)  # 50k - 2M VND
            if type_name == 'VIP':
                price = base_price * 2
            elif type_name == 'Student':
                price = base_price * 0.7
            elif type_name == 'Early Bird':
                price = base_price * 0.8
            else:
                price = base_price
            
            ticket_type = TicketType(
                event_id=event.id,
                name=type_name,
                description=fake.sentence(),
                price=Decimal(str(price)),
                total_quantity=random.randint(50, 500),
                sold_quantity=0,  # Sẽ được cập nhật khi tạo vé
                is_active=True
            )
            ticket_types.append(ticket_type)
    
    db.session.add_all(ticket_types)
    db.session.commit()
    return ticket_types

def create_discount_codes(num_codes=10):
    """Tạo mã giảm giá"""
    discount_codes = []
    
    for i in range(num_codes):
        valid_from = fake.date_time_between(start_date='-1m', end_date='now')
        valid_to = valid_from + timedelta(days=random.randint(7, 90))
        
        discount_code = DiscountCode(
            code=fake.lexify(text='DISCOUNT???').upper(),
            discount_percentage=Decimal(random.choice([5, 10, 15, 20, 25, 30])),
            valid_from=valid_from,
            valid_to=valid_to,
            user_group=random.choice(list(CustomerGroup)),
            max_uses=random.choice([None, 10, 50, 100]),
            used_count=0,
            is_active=True
        )
        discount_codes.append(discount_code)
    
    db.session.add_all(discount_codes)
    db.session.commit()
    return discount_codes

def create_tickets_and_payments(users, ticket_types, discount_codes, num_tickets=200):
    """Tạo vé và thanh toán"""
    tickets = []
    payments = []
    customers = [u for u in users if u.role == UserRole.customer]
    
    # Tạo payments trước
    for i in range(num_tickets // 3):  # Mỗi payment có thể có nhiều vé
        user = random.choice(customers)
        discount_code = random.choice(discount_codes + [None, None, None])  # 25% chance có discount
        
        payment = Payment(
            user_id=user.id,
            amount=Decimal('0'),  # Sẽ được tính sau
            payment_method=random.choice(list(PaymentMethod)),
            status=random.choice([True, True, True, False]),  # 75% thành công
            transaction_id=f'TXN_{uuid.uuid4().hex[:10].upper()}',
            discount_code_id=discount_code.id if discount_code else None
        )
        
        if payment.status:
            payment.paid_at = fake.date_time_between(start_date='-1m', end_date='now')
        
        payments.append(payment)
    
    db.session.add_all(payments)
    db.session.commit()
    
    # Tạo tickets
    total_amount_by_payment = {}
    
    for i in range(num_tickets):
        ticket_type = random.choice(ticket_types)
        user = random.choice(customers)
        payment = random.choice(payments) if payments else None
        
        ticket = Ticket(
            user_id=user.id,
            event_id=ticket_type.event_id,
            ticket_type_id=ticket_type.id,
            uuid=str(uuid.uuid4()),
            is_paid=payment.status if payment else False,
            purchase_date=payment.paid_at if payment and payment.status else None,
            is_checked_in=random.choice([True, False]) if payment and payment.status else False,
            payment_id=payment.id if payment else None
        )
        
        if ticket.is_checked_in:
            ticket.check_in_date = fake.date_time_between(
                start_date=ticket.purchase_date, 
                end_date='now'
            )
        
        tickets.append(ticket)
        
        # Cập nhật sold_quantity
        ticket_type.sold_quantity += 1
        
        # Tính tổng tiền cho payment
        if payment:
            if payment.id not in total_amount_by_payment:
                total_amount_by_payment[payment.id] = Decimal('0')
            total_amount_by_payment[payment.id] += ticket_type.price
    
    # Cập nhật amount cho các payments
    for payment in payments:
        if payment.id in total_amount_by_payment:
            base_amount = total_amount_by_payment[payment.id]
            if payment.discount_code:
                discount = base_amount * (payment.discount_code.discount_percentage / 100)
                payment.amount = base_amount - discount
                payment.discount_code.used_count += 1
            else:
                payment.amount = base_amount
    
    db.session.add_all(tickets)
    db.session.commit()
    return tickets, payments

def create_reviews(users, events, num_reviews=100):
    """Tạo đánh giá"""
    reviews = []
    customers = [u for u in users if u.role == UserRole.customer]
    
    for i in range(num_reviews):
        event = random.choice(events)
        user = random.choice(customers)
        
        # Tạo review chính
        review = Review(
            event_id=event.id,
            user_id=user.id,
            rating=random.randint(1, 5),
            comment=fake.text(max_nb_chars=200),
            created_at=fake.date_time_between(start_date='-1m', end_date='now')
        )
        reviews.append(review)
        
        # 30% chance có reply từ organizer
        if random.random() < 0.3:
            reply = Review(
                event_id=event.id,
                user_id=event.organizer_id,
                rating=review.rating,  # Reply không thay đổi rating
                comment=fake.sentence(),
                parent_review_id=None,  # Sẽ được set sau khi review chính được commit
                created_at=review.created_at + timedelta(hours=random.randint(1, 48))
            )
            reviews.append(reply)
    
    db.session.add_all(reviews)
    db.session.commit()
    
    # Cập nhật parent_review_id cho replies
    main_reviews = [r for r in reviews if r.parent_review_id is None]
    reply_reviews = [r for r in reviews if r.parent_review_id is None and r.user_id != r.event.organizer_id]
    
    for i in range(0, len(reply_reviews), 2):
        if i < len(main_reviews):
            reply_reviews[i].parent_review_id = main_reviews[i].id
    
    db.session.commit()
    return reviews

def create_notifications_and_user_notifications(users, events, num_notifications=20):
    """Tạo thông báo"""
    notifications = []
    
    notification_types = ['reminder', 'update', 'cancellation', 'new_event', 'promotion']
    
    for i in range(num_notifications):
        event = random.choice(events + [None, None])  # 33% chance không liên quan đến event cụ thể
        
        notification = Notification(
            event_id=event.id if event else None,
            title=fake.sentence(nb_words=6),
            message=fake.text(max_nb_chars=300),
            notification_type=random.choice(notification_types),
            created_at=fake.date_time_between(start_date='-1m', end_date='now')
        )
        notifications.append(notification)
    
    db.session.add_all(notifications)
    db.session.commit()
    
    # Tạo user notifications
    user_notifications = []
    customers = [u for u in users if u.role == UserRole.customer]
    
    for notification in notifications:
        # Mỗi notification gửi cho 20-80% customers
        selected_users = random.sample(customers, random.randint(len(customers)//5, len(customers)*4//5))
        
        for user in selected_users:
            user_notification = UserNotification(
                user_id=user.id,
                notification_id=notification.id,
                is_read=random.choice([True, False]),
                created_at=notification.created_at + timedelta(minutes=random.randint(1, 60))
            )
            
            if user_notification.is_read:
                user_notification.read_at = user_notification.created_at + timedelta(minutes=random.randint(1, 1440))
            
            user_notifications.append(user_notification)
    
    db.session.add_all(user_notifications)
    db.session.commit()
    return notifications, user_notifications

def create_event_trending_logs(events):
    """Tạo log trending cho events"""
    trending_logs = []
    
    for event in events:
        trending_log = EventTrendingLog(
            event_id=event.id,
            view_count=random.randint(10, 5000),
            total_revenue=Decimal(str(random.randint(1000000, 50000000))),
            trending_score=Decimal('0'),
            interest_score=Decimal('0'),
            last_updated=fake.date_time_between(start_date='-1w', end_date='now')
        )
        trending_logs.append(trending_log)
    
    db.session.add_all(trending_logs)
    db.session.commit()
    
    # Tính toán scores (nếu có method calculate_score)
    try:
        for log in trending_logs:
            if hasattr(log, 'calculate_score'):
                log.calculate_score()
    except Exception as e:
        print(f"⚠️ Không thể tính toán trending score: {e}")
    
    return trending_logs

def seed_database():
    """Chạy toàn bộ quá trình seed database"""
    print("🌱 Bắt đầu seed database...")
    try:
        # Kiểm tra xem đã có dữ liệu chưa
        # existing_users = User.query.first()
        # if existing_users:
        #     print("📊 Database đã có dữ liệu, bỏ qua seed")
        #     return

        print("🧹 Xóa dữ liệu cũ...")
        from sqlalchemy import text
        # Xóa bảng liên kết event_staff trước để tránh lỗi khóa ngoại
        db.session.execute(text('DELETE FROM event_staff;'))
        db.session.commit()
        # Xóa từng bảng một cách an toàn (không cần SET FOREIGN_KEY_CHECKS cho PostgreSQL)
        UserNotification.query.delete()
        Notification.query.delete()
        Review.query.delete()
        db.session.commit()
        EventTrendingLog.query.delete()
        Ticket.query.delete()
        Payment.query.delete()
        TicketType.query.delete()
        DiscountCode.query.delete()
        Event.query.delete()
        User.query.delete()
        db.session.commit()

        # Tạo dữ liệu mới
        print("👥 Tạo users...")
        users = create_users(50)

        print("🎉 Tạo events...")
        events = create_events(users, 30)

        print("🎫 Tạo ticket types...")
        ticket_types = create_ticket_types(events)

        print("🏷️ Tạo discount codes...")
        discount_codes = create_discount_codes(15)

        print("💳 Tạo tickets và payments...")
        tickets, payments = create_tickets_and_payments(users, ticket_types, discount_codes, 300)

        print("⭐ Tạo reviews...")
        reviews = create_reviews(users, events, 150)

        print("📢 Tạo notifications...")
        notifications, user_notifications = create_notifications_and_user_notifications(users, events, 25)

        print("📊 Tạo trending logs...")
        trending_logs = create_event_trending_logs(events)

        print("✅ Seed database hoàn thành!")
        print(f"📊 Tạo thành công:")
        print(f"   - {len(users)} users")
        print(f"   - {len(events)} events") 
        print(f"   - {len(ticket_types)} ticket types")
        print(f"   - {len(tickets)} tickets")
        print(f"   - {len(payments)} payments")
        print(f"   - {len(reviews)} reviews")
        print(f"   - {len(notifications)} notifications")
        print(f"   - {len(user_notifications)} user notifications")
        print(f"   - {len(trending_logs)} trending logs")
    except Exception as e:
        print(f"❌ Lỗi khi seed database: {e}")
        db.session.rollback()

def create_app():
    """Tạo Flask app cho việc seeding"""
    app = Flask(__name__)
    
    # Cấu hình database - sử dụng MySQL từ environment hoặc fallback về SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///eventapp.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Khởi tạo database
    db.init_app(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed_database()