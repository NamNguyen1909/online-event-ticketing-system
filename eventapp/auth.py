from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from eventapp import app, db
from eventapp.models import User, UserRole
from eventapp.dao import check_user, check_email
import re
import logging

auth_bp = Blueprint('auth', __name__)

# Khởi tạo Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def validate_email(email):
    """Kiểm tra định dạng email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Kiểm tra độ mạnh của mật khẩu"""
    if len(password) < 8:
        return False, "Mật khẩu phải dài ít nhất 8 ký tự"
    if not re.search(r'[A-Z]', password):
        return False, "Mật khẩu phải chứa ít nhất một chữ cái in hoa"
    if not re.search(r'[a-z]', password):
        return False, "Mật khẩu phải chứa ít nhất một chữ cái thường"
    if not re.search(r'[0-9]', password):
        return False, "Mật khẩu phải chứa ít nhất một số"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Mật khẩu phải chứa ít nhất một ký tự đặc biệt"
    return True, ""

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            phone = data.get('phone')
            first_name = data.get('first_name')  
            last_name = data.get('last_name')   
            cmnd = data.get('cmnd')             

            # Kiểm tra dữ liệu đầu vào
            if not all([username, email, password]):
                flash('Thiếu các trường bắt buộc (tên người dùng, email, mật khẩu)', 'danger')
                return redirect(url_for('auth.register'))

            if not validate_email(email):
                flash('Định dạng email không hợp lệ', 'danger')
                return redirect(url_for('auth.register'))

            is_valid_password, password_error = validate_password(password)
            if not is_valid_password:
                flash(password_error, 'danger')
                return redirect(url_for('auth.register'))

            # Kiểm tra xem tên người dùng hoặc email đã tồn tại chưa
            if check_user(username):
                flash('Tên người dùng đã tồn tại', 'danger')
                return redirect(url_for('auth.register'))
            if check_email(email):
                flash('Email đã tồn tại', 'danger')
                return redirect(url_for('auth.register'))

            # Tạo người dùng mới
            password_hash = generate_password_hash(password)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                role=UserRole.customer,
                phone=phone
            )
            db.session.add(user)
            db.session.commit()

            # Đăng nhập người dùng sau khi đăng ký thành công
            login_user(user)
            flash('Đăng ký thành công! Chào mừng bạn đến với EventHub.', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Đã xảy ra lỗi: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            username_or_email = data.get('username_or_email')
            password = data.get('password')
            logging.debug(f"Yêu cầu đăng nhập: username_or_email={username_or_email}")

            if not username_or_email or not password:
                flash('Thiếu tên người dùng/email hoặc mật khẩu', 'danger')
                return redirect(url_for('auth.login'))

            user = User.query.filter(
                (User.username == username_or_email) | (User.email == username_or_email)
            ).first()
            logging.debug(f"Kết quả truy vấn user: {user}")

            if not user or not check_password_hash(user.password_hash, password):
                flash('Thông tin đăng nhập không hợp lệ', 'danger')
                return redirect(url_for('auth.login'))

            if not user.is_active:
                flash('Tài khoản đã bị vô hiệu hóa', 'danger')
                return redirect(url_for('auth.login'))

            login_user(user, remember=data.get('remember_me', False))
            logging.debug(f"Đăng nhập thành công cho user: {user.username}")
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            logging.error(f"Lỗi trong quá trình đăng nhập: {str(e)}")
            flash(f'Đã xảy ra lỗi: {str(e)}', 'danger')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    try:
        logout_user()
        flash('Đăng xuất thành công', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Đã xảy ra lỗi: {str(e)}', 'danger')
        return redirect(url_for('index'))

@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    logging.debug('Bắt đầu xử lý yêu cầu /auth/kiem-tra-dang-nhap')
    try:
        if current_user.is_authenticated:
            logging.debug(f'Người dùng đã xác thực: {current_user.username}')
            return jsonify({
                'is_authenticated': True,
                'user': {
                    'id': current_user.id,
                    'username': current_user.username,
                    'email': current_user.email,
                    'role': current_user.role.value
                }
            }), 200
        else:
            logging.debug('Người dùng chưa xác thực')
            return jsonify({'is_authenticated': False}), 200
    except Exception as e:
        logging.error(f'Lỗi trong check_auth: {str(e)}')
        return jsonify({'error': 'Lỗi server nội bộ'}), 500