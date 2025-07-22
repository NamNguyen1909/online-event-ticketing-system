from eventapp import app, db

if __name__ == '__main__':
    with app.app_context():
        # Tạo bảng cơ sở dữ liệu
        db.create_all()
        print("Tạo bảng cơ sở dữ liệu thành công!")
    
    # Chạy ứng dụng
    app.run(debug=True)