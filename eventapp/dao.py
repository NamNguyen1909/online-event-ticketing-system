from sqlalchemy import or_
from eventapp.models import User
from eventapp import db

def check_user(username):
    return User.query.filter(User.username == username).first()

def check_email(email):
    return User.query.filter(User.email == email).first()

def get_user_by_username(username):
    user = User.query.filter(User.username == username).first()
    return user.id if user else None