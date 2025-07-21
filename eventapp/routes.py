from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from eventapp import app, db
from eventapp.models import Event, EventCategory, Ticket, Payment, UserNotification

@app.route("/", endpoint="index")
def index():
    featured_events = Event.query.filter_by(is_active=True).limit(3).all()
    return render_template('index.html', events=featured_events)

@app.route("/events")
def events():
    events = Event.query.filter_by(is_active=True).all()
    return render_template('events.html', events=events)

@app.route("/trending")
def trending():
    trending_events = Event.query.join(EventTrendingLog).order_by(EventTrendingLog.trending_score.desc()).limit(10).all()
    return render_template('trending.html', events=trending_events)

@app.route("/support")
def support():
    return render_template('support.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/contact")
def contact():
    return render_template('contact.html')

@app.route("/policy")
def policy():
    return render_template('policy.html')

@app.route("/terms")
def terms():
    return render_template('terms.html')

@app.route("/privacy")
def privacy():
    return render_template('privacy.html')

@app.route("/faq")
def faq():
    return render_template('faq.html')

@app.route("/category/<category>")
def category(category):
    try:
        category_enum = EventCategory[category.lower()]
        events = Event.query.filter_by(category=category_enum, is_active=True).all()
        return render_template('category.html', events=events, category=category)
    except KeyError:
        return render_template('404.html'), 404

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_detail.html', event=event)

@app.route("/profile")
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route("/my-tickets")
@login_required
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route("/my-events")
@login_required
def my_events():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    return render_template('my_events.html', events=events)

@app.route("/orders")
@login_required
def orders():
    payments = Payment.query.filter_by(user_id=current_user.id).all()
    return render_template('orders.html', payments=payments)

@app.route("/settings")
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@app.route("/notifications")
@login_required
def notifications():
    notifications = UserNotification.query.filter_by(user_id=current_user.id).order_by(UserNotification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)