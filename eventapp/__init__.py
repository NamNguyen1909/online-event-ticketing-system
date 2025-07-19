from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import cloudinary


app = Flask(__name__)

# Khai báo chuỗi kết nối DB
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:ThanhNam*1909@localhost/event"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

# Khởi tạo ORM và Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

cloudinary.config(cloud_name='dncgine9e',
                  api_key='257557947612624',
                  api_secret='88EDQ7-Ltwzn1oaI4tT_UIb_bWI')

# Import routes sau khi khởi tạo app
from eventapp import routes
