from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
import cloudinary
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Cấu hình database từ environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///eventapp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 's1f7@N0pb6$Yz!Fq3Zx#Mle*2d@9Kq')

# Cấu hình session chi tiết hơn
app.config['SESSION_COOKIE_NAME'] = 'eventapp_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # True nếu dùng HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = None  # Cho phép subdomain
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 giờ thay vì 30 phút

# Khởi tạo ORM và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Flask-Admin
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from eventapp.models import User, Event, Ticket, TicketType, DiscountCode, Payment, EventTrendingLog, Review, Notification, UserNotification, Translation
from flask_admin.base import MenuLink

admin = Admin(app, name='EventHub Admin', template_mode='bootstrap4')
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Event, db.session))
admin.add_view(ModelView(Ticket, db.session))
admin.add_view(ModelView(TicketType, db.session))
admin.add_view(ModelView(DiscountCode, db.session))
admin.add_view(ModelView(Payment, db.session))
admin.add_view(ModelView(EventTrendingLog, db.session))
admin.add_view(ModelView(Review, db.session))
admin.add_view(ModelView(Notification, db.session))
admin.add_view(ModelView(UserNotification, db.session))
admin.add_view(ModelView(Translation, db.session))
admin.add_link(MenuLink(name='Quay lại Admin Dashboard', url='/admin/dashboard'))

# Khởi tạo Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bạn cần đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'  
login_manager.refresh_view = 'auth.login'
login_manager.needs_refresh_message = 'Vui lòng đăng nhập lại để tiếp tục.'

@login_manager.user_loader
def load_user(user_id):
    from eventapp.models import User
    try:
        return User.query.get(int(user_id))
    except:
        return None

# Context processor để thêm current_user vào tất cả templates
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Middleware để debug session
# @app.before_request
# def log_session_info():
#     if app.debug:
#         from flask import request, session
#         print(f"[SESSION DEBUG] Path: {request.path}")
#         print(f"[SESSION DEBUG] User authenticated: {current_user.is_authenticated}")
#         print(f"[SESSION DEBUG] Session keys: {list(session.keys())}")
#         if '_user_id' in session:
#             print(f"[SESSION DEBUG] User ID in session: {session['_user_id']}")

# Cấu hình Cloudinary từ environment variables
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Import routes sau khi khởi tạo app
from eventapp import routes

# Import và đăng ký auth blueprint
from eventapp.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/auth')