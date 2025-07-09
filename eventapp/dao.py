import json


def auth_user(username, password):
    with open('..data/user.json', encoding='utf-8') as f:
        users = json.load(f)

    for user in users:
        if user['username'] == username and user['password'] == password:
            return True

    return False


if __name__ == "__main__":
    print(auth_user("admin", 123))
