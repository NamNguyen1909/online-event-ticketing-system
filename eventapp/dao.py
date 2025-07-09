import json
import os


def auth_user(username, password):
    # Get the directory of current file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, 'data', 'users.json')
    
    try:
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
        
        # Access users array from JSON structure
        users = data.get('users', [])
        
        for user in users:
            # Convert password to string for comparison
            if user['username'] == username and str(user['password']) == str(password):
                return True
        
        return False
    
    except FileNotFoundError:
        print(f"File not found: {json_path}")
        return False
    except json.JSONDecodeError:
        print("Invalid JSON format")
        return False


if __name__ == "__main__":
    print(auth_user("admin", "456"))
    print(auth_user("user", "123"))
