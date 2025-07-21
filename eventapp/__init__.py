from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
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


# Khởi tạo ORM và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Cấu hình Cloudinary từ environment variables
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Import routes sau khi khởi tạo app
from eventapp import routes
