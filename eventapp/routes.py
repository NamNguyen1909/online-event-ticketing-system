from eventapp import app, db
from eventapp.models import Event, TicketType, Review, User
from flask import render_template, request, abort, session
from sqlalchemy.orm import joinedload
from datetime import datetime

@app.route('/')
def home():
    return render_template('index.html')

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
        current_user = None
        can_reply = False
        
        if 'user_id' in session:
            current_user = User.query.get(session['user_id'])
            if current_user:
                # Cho phép reply nếu user là staff hoặc organizer
                can_reply = current_user.role in ['staff', 'organizer']
        
        return render_template('customer/EventDetail.html', 
                             event=event, 
                             ticket_types=active_ticket_types,
                             reviews=main_reviews,
                             stats=stats,
                             current_user=current_user,
                             can_reply=can_reply)
                             
    except Exception as e:
        print(f"Error in event_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        abort(500)

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

@app.route('/debug/events')
def debug_events():
    """Debug route để xem có events nào trong database"""
    events = Event.query.all()
    return f"Có {len(events)} events trong database: {[e.id for e in events]}"