from eventapp import app, db
from eventapp.models import User, Event, TicketType, Ticket, Payment, Review, UserNotification, DiscountCode

if __name__ == '__main__':
    with app.app_context():
        # Tạo các bảng database
        db.create_all()
        print("Database tables created successfully!")
    
    # Chạy ứng dụng
    app.run(debug=True)
