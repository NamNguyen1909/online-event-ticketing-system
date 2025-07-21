from eventapp import app, db
from eventapp.models import Event, TicketType, Review, User
from flask import render_template, request, abort
from sqlalchemy.orm import joinedload

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Chi tiết sự kiện"""
    # Load event với các thông tin liên quan (không dùng joinedload cho dynamic relationships)
    event = db.session.query(Event).options(
        joinedload(Event.organizer),
        joinedload(Event.reviews).joinedload(Review.user)
    ).filter_by(id=event_id, is_active=True).first()
    
    if not event:
        abort(404)
    
    # Lấy các ticket types đang hoạt động (query riêng vì relationship là dynamic)
    active_ticket_types = event.ticket_types.filter_by(is_active=True).all()
    
    # Lấy reviews (chỉ lấy review chính, không lấy replies)
    main_reviews = [r for r in event.reviews if r.parent_review_id is None]
    
    # Tính toán thống kê
    stats = {
        'total_tickets': event.total_tickets,
        'sold_tickets': event.sold_tickets,
        'available_tickets': event.available_tickets,
        'revenue': event.revenue,
        'average_rating': round(event.average_rating, 1) if event.average_rating else 0,
        'review_count': len(main_reviews)
    }
    
    return render_template('customer/EventDetail.html', 
                         event=event, 
                         ticket_types=active_ticket_types,
                         reviews=main_reviews[:5],  # Chỉ hiển thị 5 review đầu
                         stats=stats)

@app.route('/events')
def event_list():
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