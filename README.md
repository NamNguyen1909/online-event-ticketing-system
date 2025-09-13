# 🎟️ Online Event Ticketing System (EventHub)

[![Flask](https://img.shields.io/badge/Flask-2.3.x-blue?logo=flask)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql)](https://www.postgresql.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.x-purple?logo=bootstrap)](https://getbootstrap.com/)
[![Cloudinary](https://img.shields.io/badge/Cloudinary-Image-blue?logo=cloudinary)](https://cloudinary.com/)

## Table of Contents
- [Introduction](#introduction)
- [Features](#features)
- [Architecture](#architecture)
- [Setup Instructions](#setup-instructions)
- [Developer Workflows](#developer-workflows)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Contact](#contact)


## Introduction
**EventHub** là nền tảng bán vé sự kiện trực tuyến cho phép nhà tổ chức đăng tải, bán, quản lý vé cho các chương trình (hòa nhạc, hội thảo, thể thao, v.v.). Người dùng có thể duyệt, tìm kiếm, mua vé, nhận vé điện tử (QR code), và quản lý sự kiện dễ dàng.

🌐 **Demo/Production:** [https://eventhub-lpuu.onrender.com/](https://eventhub-lpuu.onrender.com/)

### Key Features
- **Event Discovery**: Duyệt, tìm kiếm, lọc sự kiện theo danh mục, thời gian, địa điểm
- **Ticket Purchase**: Đặt vé, chọn loại vé, số lượng, thanh toán trực tuyến
- **E-Ticket Delivery**: Nhận vé điện tử qua email, QR code check-in tại cổng
- **Organizer Dashboard**: Tạo, chỉnh sửa, quản lý sự kiện, xem doanh thu
- **Staff Tools**: Quét vé, xác thực check-in, phân quyền nhân viên
- **Payment Integration**: Hỗ trợ VNPay, Momo (có thể mở rộng)
- **Notifications**: Gửi thông báo, nhắc nhở, cập nhật cho người dùng
- **Image/QR Management**: Lưu trữ ảnh, QR code trên Cloudinary

## Architecture
```
online-event-ticketing-system/
├── eventapp/                # Main Flask app
│   ├── app.py               # App factory, config, DB setup
│   ├── index.py             # App entry point
│   ├── models.py            # SQLAlchemy models (User, Event, Ticket, ...)
│   ├── dao.py               # Business/data logic (booking, payment, ...)
│   ├── routes.py            # Flask routes (web/API)
│   ├── auth.py              # Auth logic (Flask-Login, session)
│   ├── utils.py             # Utilities (email, QR, Cloudinary)
│   ├── static/              # CSS, JS, images
│   ├── templates/           # Jinja2 templates (by role)
│   ├── migrations/          # Alembic migration scripts
│   ├── data/                # Seed data
│   └── tests/               # Unit/integration tests
├── seed.py                  # DB seeding/reset script
├── render.yaml              # Deployment config (Render.com)
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

## Setup Instructions
### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- (Optional) Cloudinary, VNPay/Momo accounts for full features

### Local Development
1. **Clone repository**
	```bash
	git clone https://github.com/NamNguyen1909/online-event-ticketing-system.git
	cd online-event-ticketing-system/eventapp
	```
2. **Create virtual environment & install dependencies**
	```bash
	python -m venv venv
	venv\Scripts\activate  # Windows
	# source venv/bin/activate  # macOS/Linux
	pip install -r requirements.txt
	```
3. **Configure environment**
	- Tạo file `.env` với các biến: `DATABASE_URL`, `CLOUDINARY_*`, SMTP, ...
4. **Database migration**
	```bash
	flask db migrate -m "Initial migration"
	flask db upgrade
	```
5. **Seed database (optional)**
	```bash
	python ../seed.py
	```
6. **Run app**
	```bash
	set FLASK_APP=app.py && set FLASK_ENV=development && flask run
	# hoặc
	python index.py
	```
7. Truy cập: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

## Developer Workflows
- **Migrations**: `flask db migrate -m "msg"` → `flask db upgrade`
- **Testing**: `pytest` hoặc `python -m unittest` trong `eventapp/tests/`
- **Seeding**: `python seed.py`
- **CI/CD**: Xem `render.yaml` để biết quy trình build, migrate, seed khi deploy
- **Debugging**: Sử dụng Flask debug mode, kiểm tra log, test với session giả lập user_id

## API Endpoints (Sample)
- `GET /event/<id>`: Xem chi tiết sự kiện
- `POST /booking/process`: Đặt vé (yêu cầu đăng nhập)
- `POST /staff/scan-ticket`: Quét vé QR (staff)
- `POST /auth/login`: Đăng nhập
- `POST /auth/register`: Đăng ký

## Deployment
+### Render.com (hoặc server riêng)
- Build/Deploy: Xem `render.yaml` (chạy migrate, seed tự động)
- Env: Đặt biến môi trường cho DB, Cloudinary, SMTP, ...
- Database: PostgreSQL (tạo trước khi deploy)
+- **Deployed site:** [https://eventhub-lpuu.onrender.com/](https://eventhub-lpuu.onrender.com/)

## Contributing
1. Fork & clone repo
2. Tạo branch mới cho feature/bugfix
3. Commit code, viết test nếu thêm logic
4. Pull request kèm mô tả rõ ràng

## Contact
- **Nam Nguyen**: namnguyen19092004@gmail.com
- **HwPhuc**: phuc.lehw@gmail.com
- **FongFus**: npphus@gmail.com

**Built with ❤️ for modern event management**
