from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import cloudinary
import os

app = Flask(__name__)

# Cấu hình ứng dụng
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:Admin%40123@localhost/event"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')

# Khởi tạo ORM và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Cấu hình Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', 'dncgine9e'),
    api_key=os.getenv('CLOUDINARY_API_KEY', '257557947612624'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET', '88EDQ7-Ltwzn1oaI4tT_UIb_bWI')
)

# Import routes sau khi khởi tạo app
try:
    from eventapp import routes
except ImportError:
    print("Warning: routes module not found. Skipping import.")