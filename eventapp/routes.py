from eventapp import app, db, login_manager
from eventapp.models import PaymentMethod, EventCategory, UserRole, User, Event
from eventapp import dao
from flask import flash, jsonify, render_template, request, abort, session, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateTimeLocalField, FloatField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from datetime import datetime
from werkzeug.security import generate_password_hash
from eventapp.auth import validate_email, validate_password
from sqlalchemy.orm import joinedload
import logging

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
    title = StringField('Tiêu Đề', validators=[DataRequired(), Length(min=3, max=255)])
    description = TextAreaField('Mô Tả', validators=[DataRequired(), Length(max=5000)])
    category = SelectField('Danh Mục', validators=[DataRequired()], choices=[(cat.value, cat.name.title()) for cat in EventCategory])
    start_time = DateTimeLocalField('Thời Gian Bắt Đầu', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    end_time = DateTimeLocalField('Thời Gian Kết Thúc', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    location = StringField('Địa Điểm', validators=[DataRequired(), Length(max=500)])
    ticket_name = StringField('Tên Vé', validators=[DataRequired(), Length(max=100)])
    price = FloatField('Giá', validators=[DataRequired(), NumberRange(min=0)])
    ticket_quantity = IntegerField('Số Lượng Vé', validators=[DataRequired(), NumberRange(min=1)])
    poster = FileField('Poster', validators=[Optional(), FileAllowed(['jpg', 'png'], 'Chỉ cho phép ảnh!')])

    def validate_end_time(self, field):
        if self.start_time.data >= field.data:
            raise ValidationError('Thời gian kết thúc phải sau thời gian bắt đầu.')

# Form for update event (similar, but optional for some)
class UpdateEventForm(CreateEventForm):
    title = StringField('Tiêu Đề', validators=[Optional(), Length(min=3, max=255)])
    description = TextAreaField('Mô Tả', validators=[Optional(), Length(max=5000)])
    category = SelectField('Danh Mục', validators=[Optional()], choices=[(cat.value, cat.name.title()) for cat in EventCategory])
    start_time = DateTimeLocalField('Thời Gian Bắt Đầu', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    end_time = DateTimeLocalField('Thời Gian Kết Thúc', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    location = StringField('Địa Điểm', validators=[Optional(), Length(max=500)])
    ticket_name = StringField('Tên Vé', validators=[Optional(), Length(max=100)])
    price = FloatField('Giá', validators=[Optional(), NumberRange(min=0)])
    ticket_quantity = IntegerField('Số Lượng Vé', validators=[Optional(), NumberRange(min=1)])
    poster = FileField('Poster', validators=[Optional(), FileAllowed(['jpg', 'png'], 'Chỉ cho phép ảnh!')])

@app.route('/')
def index():
    """ Trang chủ"""
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
                             can_reply=can_reply)
                             
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
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)

    events = dao.search_events(page, 12, category, search, start_date, end_date, min_price, max_price)
    return render_template('customer/EventList.html', events=events)

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
    
    return render_template('customer/EventList.html', 
                  events=events, 
                  category=category,
                  category_title=category_title)

@app.route('/admin/dashboard', methods=['GET'])
@login_required
def admin_dashboard():
    """Bảng điều khiển admin để hiển thị báo cáo doanh thu cho tất cả sự kiện"""
    if current_user.role.value != 'admin':
        abort(403)  # Cấm nếu không phải admin

    try:
        # Lấy tất cả sự kiện với ticket types bằng eager loading
        events = db.session.query(Event).options(
            joinedload(Event.ticket_types)
        ).filter_by(is_active=True).all()

        # Tính toán thống kê cho mỗi sự kiện
        stats = []
        total_revenue = 0
        for event in events:
            active_ticket_types = [tt for tt in event.ticket_types if tt.is_active]
            stat = dao.calculate_event_stats(active_ticket_types, event.reviews.all())
            stats.append({
                'event_id': event.id,
                'title': event.title,
                'total_tickets': stat['total_tickets'],
                'sold_tickets': stat['sold_tickets'],
                'available_tickets': stat['available_tickets'],
                'revenue': stat['revenue']
            })
            total_revenue += stat['revenue']

        # Chuẩn bị dữ liệu cho Chart.js
        chart_data = {
            'labels': [event.title for event in events],
            'revenues': [stat['revenue'] for stat in stats]
        }

        return render_template('admin/AdminDashboard.html',
                             stats=stats,
                             total_revenue=total_revenue,
                             chart_data=chart_data)

    except Exception as e:
        logging.error(f"Lỗi trong admin_dashboard: {str(e)}")
        abort(500)

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/test-session')
def test_session():
    """Kiểm tra session và trạng thái xác thực"""
    session_info = {
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
    """Kiểm tra trạng thái xác thực"""
    if current_user.is_authenticated:
        return f"<h2>Đã đăng nhập</h2><p>User: {current_user.username}</p><p>ID: {current_user.id}</p>"
    else:
        return f"<h2>Chưa đăng nhập</h2><p><a href='{url_for('auth.login')}'>Đăng nhập</a></p>"

# Các tuyến đường cho người tổ chức
@app.route('/organizer/dashboard', methods=['GET'])
@login_required
def organizer_dashboard():
    """Bảng điều khiển người tổ chức"""
    if current_user.role.value != 'organizer':
        abort(403)
    logging.debug(f"Truy cập bảng điều khiển người tổ chức cho người dùng: {current_user.username}")
    return redirect(url_for('organizer_my_events'))

@app.route('/organizer/create-event', methods=['GET', 'POST'])
@login_required
def organizer_create_event():
    """Tạo sự kiện mới"""
    if current_user.role.value != 'organizer':
        abort(403)
    
    form = CreateEventForm()
    if form.validate_on_submit():
        try:
            data = form.data
            event = dao.create_event(data, current_user.id)
            flash('Tạo sự kiện thành công!', 'success')
            return redirect(url_for('organizer_my_events'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi tạo sự kiện: {str(e)}', 'danger')
    
    return render_template('organizer/CreateEvent.html', form=form)

@app.route('/organizer/my-events', methods=['GET'])
@login_required
def organizer_my_events():
    """Hiển thị danh sách sự kiện của người tổ chức"""
    if current_user.role.value != 'organizer':
        abort(403)
    
    events = dao.get_user_events(current_user.id)
    return render_template('organizer/MyEvents.html', events=events)

@app.route('/organizer/revenue-reports', methods=['GET'])
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

@app.route('/organizer/manage-staff', methods=['GET'])
@login_required
def organizer_manage_staff():
    """Quản lý nhân viên"""
    if current_user.role.value != 'organizer':
        abort(403)
    staff = current_user.created_staff.all()
    return render_template('organizer/ManageStaff.html', staff=staff)

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
            return redirect(url_for('organizer_manage_staff'))
        staff.role = UserRole[role]
        db.session.commit()
        flash('Cập nhật vai trò thành công!', 'success')
        return redirect(url_for('organizer_manage_staff'))
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi: {str(e)}', 'danger')
        return redirect(url_for('organizer_manage_staff'))

@app.route('/organizer/add-staff', methods=['POST'])
@login_required
def add_organizer_staff():
    if current_user.role.value != 'organizer':
        abort(403)
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
        db.session.flush()  # Để có ID

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

@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"Trang không tìm thấy: {request.url}")
    return render_template('404.html'), 404