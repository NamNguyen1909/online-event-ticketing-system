from eventapp import app, db, login_manager
from eventapp.models import PaymentMethod, EventCategory, UserRole, User, Event, Ticket, TicketType
from eventapp import dao
from flask import flash, jsonify, render_template, request, abort, session, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateTimeLocalField, FloatField, IntegerField, DecimalField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from eventapp.auth import validate_email, validate_password
import logging
import uuid

# Đăng ký bộ lọc
def get_category_title(category):
    """Bộ lọc để lấy tiêu đề danh mục từ giá trị enum"""
    return dao.get_category_title(category)

def format_currency(value):
    """Bộ lọc để định dạng giá tiền thành VNĐ"""
    try:
        return f"{value:,.0f} VNĐ"
    except:
        return value

app.jinja_env.filters['get_category_title'] = get_category_title
app.jinja_env.filters['format_currency'] = format_currency

# Custom validator for start < end
class TimeComparison(object):
    def __init__(self, fieldname, message=None):
        self.fieldname = fieldname
        if not message:
            message = 'Thời gian bắt đầu phải trước thời gian kết thúc.'
        self.message = message

    def __call__(self, form, field):
        other = form[self.fieldname]
        if field.data <= other.data:
            raise ValidationError(self.message)

# Form for create event
class CreateEventForm(FlaskForm):
    ticket_name = StringField("Tên vé", validators=[DataRequired(), Length(min=3, max=255)])
    title = StringField('Tiêu Đề', validators=[DataRequired(), Length(min=3, max=255)])
    description = TextAreaField('Mô Tả', validators=[DataRequired(), Length(max=5000)])
    category = SelectField('Danh Mục', validators=[DataRequired()], choices=[(cat.value, cat.name.title()) for cat in EventCategory])
    price = DecimalField("Giá vé", validators=[DataRequired(), NumberRange(min=0)], places=2)
    start_time = DateTimeLocalField('Thời Gian Bắt Đầu', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    end_time = DateTimeLocalField('Thời Gian Kết Thúc', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    location = StringField('Địa Điểm', validators=[DataRequired(), Length(max=500)])
    poster = FileField('Poster', validators=[Optional(), FileAllowed(['jpg', 'png'], 'Chỉ cho phép ảnh!')])
    ticket_quantity = IntegerField("Số lượng vé", validators=[
        DataRequired(),
        NumberRange(min=1, message="Số lượng phải lớn hơn 0")
    ])

    def validate_end_time(self, field):
        if self.start_time.data >= field.data:
            raise ValidationError('Thời gian kết thúc phải sau thời gian bắt đầu.')

# Form for update event
class UpdateEventForm(FlaskForm):
    title = StringField('Tiêu Đề', validators=[Optional(), Length(min=3, max=255)])
    description = TextAreaField('Mô Tả', validators=[Optional(), Length(max=5000)])
    category = SelectField('Danh Mục', validators=[Optional()], choices=[(cat.value, cat.name.title()) for cat in EventCategory])
    start_time = DateTimeLocalField('Thời Gian Bắt Đầu', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    end_time = DateTimeLocalField('Thời Gian Kết Thúc', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    location = StringField('Địa Điểm', validators=[Optional(), Length(max=500)])
    poster = FileField('Poster', validators=[Optional(), FileAllowed(['jpg', 'png'], 'Chỉ cho phép ảnh!')])

    def validate_end_time(self, field):
        if self.start_time.data and field.data and self.start_time.data >= field.data:
            raise ValidationError('Thời gian kết thúc phải sau thời gian bắt đầu.')

@app.route('/')
def index():
    """Trang chủ"""
    featured_events = dao.get_featured_events()
    return render_template('index.html', events=featured_events)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Chi tiết sự kiện"""
    try:
        logging.debug(f"Tìm kiếm sự kiện với ID: {event_id}")
        
        # Load event với organizer
        event = dao.get_event_detail(event_id)
        
        if not event:
            logging.debug(f"Sự kiện với ID {event_id} không tìm thấy hoặc không hoạt động")
            abort(404)
        
        logging.debug(f"Đã tìm thấy sự kiện: {event.title}, Danh mục: {event.category}")
        
        # Lấy các ticket types đang hoạt động
        active_ticket_types = dao.get_active_ticket_types(event.id)
        logging.debug(f"Đã tìm thấy {len(active_ticket_types)} loại vé đang hoạt động")
        
        # Lấy reviews
        main_reviews = dao.get_event_reviews(event.id)
        logging.debug(f"Đã tìm thấy {len(main_reviews)} đánh giá")
        
        # Lấy tất cả reviews để tính rating
        all_reviews = dao.get_all_event_reviews(event.id)
        
        # Tính toán thống kê
        stats = dao.calculate_event_stats(active_ticket_types, all_reviews)
        logging.debug(f"Thống kê được tính toán: {stats}")
        
        # Kiểm tra quyền trả lời review
        can_reply = False
        if current_user.is_authenticated:
            can_reply = current_user.role.value in ['staff', 'organizer']
        
        return render_template('customer/EventDetail.html', 
                             event=event, 
                             ticket_types=active_ticket_types,
                             reviews=main_reviews,
                             stats=stats,
                             can_reply=can_reply,
                             dao=dao)
                             
    except Exception as e:
        logging.error(f"Lỗi trong event_detail: {str(e)}")
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

    # Xử lý quick_date
    today = datetime.today()
    if quick_date == 'today':
        start_date = today.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    elif quick_date == 'tomorrow':
        tomorrow = today + timedelta(days=1)
        start_date = tomorrow.strftime('%Y-%m-%d')
        end_date = tomorrow.strftime('%Y-%m-%d')
    elif quick_date == 'weekend':
        saturday = today + timedelta((5 - today.weekday()) % 7)
        sunday = saturday + timedelta(days=1)
        start_date = saturday.strftime('%Y-%m-%d')
        end_date = sunday.strftime('%Y-%m-%d')
    elif quick_date == 'month':
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        next_month = today.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        end_date = last_day.strftime('%Y-%m-%d')

    # Xử lý miễn phí
    if free:
        price_max = 0

    # Lấy danh sách thể loại cho dropdown
    categories = list(EventCategory)

    events = dao.search_events(page, 12, category, search, start_date, end_date, location, price_min, price_max)
    category_title = None
    if category:
        category_title = dao.get_category_title(category)
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
    return render_template('profile.html', user=current_user)

@app.route('/my-tickets')
@login_required
def my_tickets():
    tickets = dao.get_user_tickets(current_user.id)
    return render_template('my_tickets.html', tickets=tickets)

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

@app.route('/staff/scan')
@login_required
def staff_scan():
    if current_user.role.value != 'staff':
        abort(403)
    return render_template('staff/scan.html')

@app.route('/organizer/dashboard')
@login_required
def organizer_dashboard():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/dashboard.html')

@app.route('/organizer/create-event', methods=['GET', 'POST'])
@login_required
def organizer_create_event():
    """Tạo sự kiện mới với loại vé động"""
    if current_user.role.value != 'organizer':
        abort(403)
    
    form = CreateEventForm()
    if form.validate_on_submit():
        try:
            data = {
                'title': form.title.data,
                'description': form.description.data,
                'category': form.category.data,
                'start_time': form.start_time.data,
                'end_time': form.end_time.data,
                'location': form.location.data,
                'poster': form.poster.data,
                'ticket_types': []
            }
            ticket_names = request.form.getlist('ticket_names[]')
            ticket_prices = request.form.getlist('ticket_prices[]')
            ticket_quantities = request.form.getlist('ticket_quantities[]')
            for i in range(len(ticket_names)):
                data['ticket_types'].append({
                    'name': ticket_names[i],
                    'price': float(ticket_prices[i]),
                    'total_quantity': int(ticket_quantities[i])
                })
            dao.create_event_with_tickets(data, current_user.id)
            flash('Tạo sự kiện thành công!', 'success')
            return redirect(url_for('organizer_my_events'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi: {str(e)}', 'danger')
    
    return render_template('organizer/CreateEvent.html', form=form)

@app.route('/organizer/my-events', methods=['GET', 'POST'])
@login_required
def organizer_my_events():
    """Hiển thị danh sách sự kiện của người tổ chức và xử lý cập nhật sự kiện"""
    if current_user.role.value != 'organizer':
        abort(403)
    
    if request.method == 'POST':
        form = UpdateEventForm()
        if form.validate_on_submit():
            try:
                event_id = request.form.get('event_id', type=int)
                if not event_id:
                    flash('Không tìm thấy ID sự kiện', 'danger')
                    return redirect(url_for('organizer_my_events'))
                
                event = dao.get_event_detail(event_id)
                if not event or event.organizer_id != current_user.id:
                    flash('Sự kiện không tồn tại hoặc bạn không có quyền chỉnh sửa', 'danger')
                    return redirect(url_for('organizer_my_events'))
                
                data = form.data
                dao.update_event(event_id, data, current_user.id)
                flash('Cập nhật sự kiện thành công!', 'success')
                return redirect(url_for('organizer_my_events'))
            except Exception as e:
                db.session.rollback()
                flash(f'Lỗi khi cập nhật sự kiện: {str(e)}', 'danger')
                logging.error(f"Lỗi khi cập nhật sự kiện: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Lỗi ở trường {field}: {error}', 'danger')
    
    page = request.args.get('page', 1, type=int)
    events = dao.get_user_events(current_user.id, page=page, per_page=10)
    return render_template('organizer/MyEvents.html', events=events, dao=dao, form=UpdateEventForm())

@app.route('/organizer/update-event/<int:event_id>', methods=['POST'])
@login_required
def update_event_route(event_id):
    """Cập nhật sự kiện với loại vé động"""
    if current_user.role.value != 'organizer':
        abort(403)
    try:
        form = UpdateEventForm()
        if form.validate_on_submit():
            data = {
                'title': form.title.data,
                'description': form.description.data,
                'category': form.category.data,
                'start_time': form.start_time.data,
                'end_time': form.end_time.data,
                'location': form.location.data,
                'poster': form.poster.data,
                'ticket_types': []
            }
            ticket_ids = request.form.getlist('ticket_type_ids[]')
            ticket_names = request.form.getlist('ticket_names[]')
            ticket_prices = request.form.getlist('ticket_prices[]')
            ticket_quantities = request.form.getlist('ticket_quantities[]')
            
            for i in range(len(ticket_names)):
                if not ticket_names[i]:
                    flash('Tên vé không được để trống.', 'danger')
                    return render_template('organizer/MyEvents.html', form=form, events=dao.get_user_events(current_user.id))
                try:
                    price = float(ticket_prices[i])
                    quantity = int(ticket_quantities[i])
                except ValueError:
                    flash('Giá vé hoặc số lượng không hợp lệ.', 'danger')
                    return render_template('organizer/MyEvents.html', form=form, events=dao.get_user_events(current_user.id))
                    
                data['ticket_types'].append({
                    'id': ticket_ids[i] if ticket_ids[i] else None,
                    'name': ticket_names[i],
                    'price': price,
                    'total_quantity': quantity
                })
                
            dao.update_event_with_tickets(event_id, data, current_user.id)
            flash('Cập nhật sự kiện thành công!', 'success')
            return redirect(url_for('organizer_my_events'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Lỗi ở trường {field}: {error}', 'danger')
            return render_template('organizer/MyEvents.html', form=form, events=dao.get_user_events(current_user.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi: {str(e)}', 'danger')
        return render_template('organizer/MyEvents.html', form=form, events=dao.get_user_events(current_user.id))

@app.route('/organizer/delete-event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    """Xóa sự kiện"""
    try:
        if current_user.role.value != 'organizer':
            return jsonify({'success': False, 'message': 'Không có quyền truy cập'}), 403
        
        dao.delete_event(event_id, current_user.id)
        return jsonify({'success': True, 'message': 'Xóa sự kiện thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Lỗi khi xóa sự kiện: {str(e)}'}), 500

@app.route('/organizer/bulk-delete-events', methods=['POST'])
@login_required
def bulk_delete_events():
    """Xóa nhiều sự kiện"""
    try:
        if current_user.role.value != 'organizer':
            return jsonify({'success': False, 'message': 'Không có quyền truy cập'}), 403
        
        data = request.json
        event_ids = data.get('event_ids', [])
        if not event_ids:
            return jsonify({'success': False, 'message': 'Không có sự kiện nào được chọn'}), 400
        
        dao.bulk_delete_events(event_ids, current_user.id)
        return jsonify({'success': True, 'message': 'Xóa các sự kiện thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Lỗi khi xóa sự kiện: {str(e)}'}), 500

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
    staff = current_user.created_staff.all()
    return render_template('organizer/staff_management.html', staff=staff)

@app.route('/organizer/add-staff', methods=['GET', 'POST'])
@login_required
def add_organizer_staff():
    if current_user.role.value != 'organizer':
        abort(403)
    if request.method == 'POST':
        try:
            data = request.form
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            phone = data.get('phone')
            event_id = data.get('event_id')

            if not username or not email or not password:
                return jsonify({'success': False, 'message': 'Thiếu thông tin bắt buộc'})

            if dao.check_user(username):
                return jsonify({'success': False, 'message': 'Tên người dùng đã tồn tại'})

            if dao.check_email(email):
                return jsonify({'success': False, 'message': 'Email đã tồn tại'})

            if not validate_email(email):
                return jsonify({'success': False, 'message': 'Định dạng email không hợp lệ'})

            is_valid, msg = validate_password(password)
            if not is_valid:
                return jsonify({'success': False, 'message': msg})

            password_hash = generate_password_hash(password)
            new_staff = User(
                username=username,
                email=email,
                password_hash=password_hash,
                role=UserRole.staff,
                phone=phone,
                creator_id=current_user.id,
                is_active=True
            )
            db.session.add(new_staff)
            db.session.flush()

            if event_id:
                event = Event.query.get(int(event_id))
                if event and event.organizer_id == current_user.id:
                    event.staff.append(new_staff)
                else:
                    return jsonify({'success': False, 'message': 'Không có quyền gán cho sự kiện này'})

            db.session.commit()
            return jsonify({'success': True, 'message': 'Thêm nhân viên thành công!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    return render_template('organizer/add_staff.html')

@app.route('/organizer/staff-permissions')
@login_required
def staff_permissions():
    if current_user.role.value != 'organizer':
        abort(403)
    return render_template('organizer/permissions.html')

@app.route('/organizer/update-staff', methods=['POST'])
@login_required
def organizer_update_staff():
    """Cập nhật vai trò nhân viên"""
    if current_user.role.value != 'organizer':
        abort(403)
    try:
        staff_id = request.form.get('staff_id')
        role = request.form.get('role')
        staff = User.query.get(staff_id)
        if not staff or staff.creator_id != current_user.id:
            flash('Nhân viên không hợp lệ', 'danger')
            return redirect(url_for('manage_staff'))
        staff.role = UserRole[role]
        db.session.commit()
        flash('Cập nhật vai trò thành công!', 'success')
        return redirect(url_for('manage_staff'))
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi: {str(e)}', 'danger')
        return redirect(url_for('manage_staff'))

@app.route('/organizer/assign-staff/<int:event_id>', methods=['POST'])
@login_required
def assign_staff_to_event(event_id):
    if current_user.role.value != 'organizer':
        abort(403)
    try:
        data = request.json
        staff_id = data.get('staff_id')
        if not staff_id:
            return jsonify({'success': False, 'message': 'Thiếu staff_id'})

        staff = User.query.get(staff_id)
        if not staff or staff.role != UserRole.staff or staff.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Nhân viên không hợp lệ hoặc không thuộc quyền quản lý'})

        event = Event.query.get(event_id)
        if not event or event.organizer_id != current_user.id:
            return jsonify({'success': False, 'message': 'Sự kiện không tồn tại hoặc không thuộc quyền quản lý'})

        if staff in event.staff:
            return jsonify({'success': False, 'message': 'Nhân viên đã được gán'})

        event.staff.append(staff)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Gán nhân viên thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/organizer/event/<int:event_id>/staff', methods=['GET'])
@login_required
def get_event_staff(event_id):
    if current_user.role.value != 'organizer':
        abort(403)
    event = Event.query.get(event_id)
    if not event or event.organizer_id != current_user.id:
        abort(404)
    staff_list = [{
        'id': s.id,
        'username': s.username,
        'email': s.email
    } for s in event.staff]
    return jsonify({'success': True, 'staff': staff_list})

@app.route('/organizer/remove-staff/<int:event_id>', methods=['POST'])
@login_required
def remove_staff_from_event(event_id):
    if current_user.role.value != 'organizer':
        abort(403)
    try:
        data = request.json
        staff_id = data.get('staff_id')
        if not staff_id:
            return jsonify({'success': False, 'message': 'Thiếu staff_id'})

        staff = User.query.get(staff_id)
        if not staff or staff.role != UserRole.staff or staff.creator_id != current_user.id:
            return jsonify({'success': False, 'message': 'Nhân viên không hợp lệ hoặc không thuộc quyền quản lý'})

        event = Event.query.get(event_id)
        if not event or event.organizer_id != current_user.id:
            return jsonify({'success': False, 'message': 'Sự kiện không tồn tại hoặc không thuộc quyền quản lý'})

        if staff not in event.staff:
            return jsonify({'success': False, 'message': 'Nhân viên chưa được gán cho sự kiện này'})

        event.staff.remove(staff)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Xóa gán nhân viên thành công!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/organizer/revenue-reports')
@login_required
def organizer_revenue_reports():
    """Báo cáo doanh thu cho người tổ chức"""
    if current_user.role.value != 'organizer':
        abort(403)
    
    try:
        stats, total_revenue = dao.get_all_events_revenue_stats()
        stats = [stat for stat in stats if Event.query.get(stat['event_id']).organizer_id == current_user.id]
        return render_template('organizer/RevenueReports.html', stats=stats, total_revenue=total_revenue)
    except Exception as e:
        logging.error(f"Lỗi trong organizer_revenue_reports: {str(e)}")
        abort(500)

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
        logging.debug(f"[BOOK_TICKET] User {current_user.username} accessing event {event_id}")
        
        # Load event
        event = dao.get_event_for_booking(event_id)
        
        if not event:
            logging.debug(f"[BOOK_TICKET] Event {event_id} not found or not active")
            flash('Sự kiện không tồn tại hoặc đã bị xóa.', 'error')
            return redirect(url_for('events'))
        
        logging.debug(f"[BOOK_TICKET] Found event: {event.title}")
        
        # Load ticket types
        all_ticket_types = dao.get_all_ticket_types_for_event(event_id)
        logging.debug(f"[BOOK_TICKET] Event has {len(all_ticket_types)} ticket types")
        
        # Lấy các ticket types khả dụng
        available_ticket_types = dao.get_available_ticket_types(all_ticket_types)
        logging.debug(f"[BOOK_TICKET] Available ticket types: {len(available_ticket_types)}")
        
        if not available_ticket_types:
            logging.debug(f"[BOOK_TICKET] No available tickets for event {event_id}")
            flash('Sự kiện này hiện tại đã hết vé.', 'warning')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # Lấy nhóm khách hàng
        user_group = dao.get_user_customer_group(current_user)
        logging.debug(f"[BOOK_TICKET] User group: {user_group}")

        # Lấy mã giảm giá
        available_discounts = dao.get_user_discount_codes(user_group)
        logging.debug(f"[BOOK_TICKET] Found {len(available_discounts)} discount codes")
        
        logging.debug(f"[BOOK_TICKET] Rendering BookTicket.html")
        return render_template('customer/BookTicket.html', 
                             event=event,
                             ticket_types=available_ticket_types,
                             discount_codes=available_discounts,
                             payment_methods=PaymentMethod)
                             
    except Exception as e:
        logging.error(f"[BOOK_TICKET] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Đã xảy ra lỗi khi tải trang đặt vé.', 'error')
        return redirect(url_for('index'))

@app.route('/booking/process', methods=['POST'])
@login_required
def process_booking():
    """Xử lý đặt vé (AJAX)"""
    dao.cleanup_unpaid_tickets()
    
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        tickets_data = data.get('tickets')
        
        # Log thông tin booking
        logging.debug("=== BOOKING INFORMATION ===")
        logging.debug(f"User: {current_user.username} (ID: {current_user.id})")
        logging.debug(f"Event ID: {data.get('event_id')}")
        logging.debug(f"Tickets: {data.get('tickets')}")
        logging.debug(f"Payment Method: {data.get('payment_method')}")
        logging.debug(f"Discount Code: {data.get('discount_code', 'None')}")
        logging.debug(f"Subtotal: {data.get('subtotal')}")
        logging.debug(f"Discount Amount: {data.get('discount_amount')}")
        logging.debug(f"Total Amount: {data.get('total_amount')}")
        logging.debug("========================")
        
        # Validation
        if not tickets_data or len(tickets_data) == 0:
            return jsonify({'success': False, 'message': 'Vui lòng chọn ít nhất một loại vé.'})
        
        total_tickets = sum(ticket['quantity'] for ticket in tickets_data)
        if total_tickets == 0:
            return jsonify({'success': False, 'message': 'Vui lòng chọn ít nhất một vé.'})
        
        # Kiểm tra tồn kho
        is_valid, error_message = dao.validate_ticket_availability(tickets_data)
        if not is_valid:
            return jsonify({'success': False, 'message': error_message})

        # Nếu chọn VNPay
        if payment_method == 'vnpay':
            transaction_id = f"VNPAY_{uuid.uuid4().hex[:12]}"
            payment = dao.create_payment(
                user_id=current_user.id,
                amount=data['total_amount'],
                payment_method=payment_method,
                status=False,
                transaction_id=transaction_id,
                discount_code=data.get('discount_code')
            )
            db.session.commit()

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
            db.session.commit()

            payment_url = dao.create_payment_url_flask(data['total_amount'], txn_ref=transaction_id)
            return jsonify({'success': True, 'payment_url': payment_url})
        
        return jsonify({'success': True, 'message': 'Đặt vé thành công!'})
        
    except Exception as e:
        logging.error(f"Error in process_booking: {str(e)}")
        return jsonify({'success': False, 'message': 'Đã xảy ra lỗi khi xử lý đặt vé.'})

@app.route('/vnpay/create_payment', methods=['POST'])
def vnpay_create_payment():
    data = request.get_json()
    amount = data.get('amount')
    txn_ref = data.get('txn_ref')
    payment_url = dao.create_payment_url_flask(amount, txn_ref)
    return jsonify({'payment_url': payment_url})

@app.route('/vnpay/redirect')
def vnpay_redirect():
    return dao.vnpay_redirect_flask()

@app.route('/tickets/cleanup', methods=['POST'])
def cleanup_unpaid_tickets():
    dao.cleanup_unpaid_tickets()
    return jsonify({'success': True, 'message': 'Cleanup unpaid tickets called'})

@app.route('/debug/session')
def debug_session():
    """Debug session info"""
    import json
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

@app.route('/api/event/<int:event_id>', methods=['GET'])
@login_required
def get_event_data(event_id):
    """Lấy chi tiết sự kiện qua API"""
    try:
        if current_user.role.value != 'organizer':
            return jsonify({'success': False, 'message': 'Không có quyền truy cập'}), 403
        
        event = dao.get_event_detail(event_id)
        if not event or event.organizer_id != current_user.id:
            return jsonify({'success': False, 'message': 'Sự kiện không tồn tại hoặc không thuộc quyền quản lý'}), 404
        
        ticket_type = event.ticket_types.first()
        return jsonify({
            'success': True,
            'event': {
                'title': event.title,
                'category': event.category.value,
                'description': event.description,
                'location': event.location,
                'ticket_quantity': ticket_type.total_quantity if ticket_type else 0,
                'price': ticket_type.price if ticket_type else 0,
                'start_time': event.start_time.strftime('%Y-%m-%dT%H:%M'),
                'end_time': event.end_time.strftime('%Y-%m-%dT%H:%M')
            }
        })
    except Exception as e:
        logging.error(f"Lỗi khi lấy dữ liệu sự kiện {event_id}: {str(e)}")
        return jsonify({'success': False, 'message': f'Lỗi khi tải dữ liệu sự kiện: {str(e)}'}), 500

@app.route('/organizer/event/<int:event_id>', methods=['GET'])
@login_required
def get_event_data_full(event_id):
    """Lấy toàn bộ chi tiết sự kiện với các loại vé"""
    if current_user.role.value != 'organizer':
        abort(403)
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    return jsonify({
        'id': event.id,
        'title': event.title,
        'category': event.category.value,
        'description': event.description,
        'location': event.location,
        'start_time': event.start_time.isoformat(),
        'end_time': event.end_time.isoformat(),
        'poster_url': event.poster_url,
        'ticket_types': [{
            'id': tt.id,
            'name': tt.name,
            'price': float(tt.price),
            'total_quantity': tt.total_quantity
        } for tt in event.ticket_types]
    })

@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"Trang không tìm thấy: {request.url}")
    return render_template('404.html'), 404