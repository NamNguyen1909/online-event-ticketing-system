# online-event-ticketing-system

### ĐỀ TÀI 5: HỆ THỐNG BÁN VÉ SỰ KIỆN TRỰC TUYẾN
Đây là một nền tảng trực tuyến cho phép các nhà tổ chức sự kiện đăng tải và bán vé cho
các chương trình của họ, từ các buổi hòa nhạc, hội thảo, đến các trận đấu thể thao. Người
dùng có thể dễ dàng tìm kiếm, mua vé và nhận vé điện tử một cách tiện lợi. Bao gồm các
yêu cầu sau:
- Yêu cầu 1: Duyệt và tìm kiếm các sự kiện
- Yêu cầu 2: Xem chi tiết sự kiện và chọn loại vé
- Yêu cầu 3: Thanh toán và nhận vé điện tử
- Yêu cầu 4: Tạo và quản lý sự kiện
- Yêu cầu 5: Theo dõi doanh thu và quét vé tại cổng




#### Tạo migration script từ thay đổi model
```
flask db migrate -m "Initial migration"
```

#### Apply migration vào DB
```
flask db upgrade
```


# RUN
```
set FLASK_APP=app.py && set FLASK_ENV=development && flask run

python index.py
```


http://127.0.0.1:5000/event/<id>