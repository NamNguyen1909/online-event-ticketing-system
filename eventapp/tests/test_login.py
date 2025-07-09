import unittest
import sys
import os

# Add parent directory to path to import dao module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dao import auth_user


class TestLogin(unittest.TestCase):
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        self.assertTrue(auth_user("admin", "456"))
    
    def test_user_login_success(self):
        """Test user login with correct credentials"""
        self.assertTrue(auth_user("user", "123"))
    
    def test_admin_login_wrong_password(self):
        """Test admin login with wrong password"""
        self.assertFalse(auth_user("admin", "123"))
    
    def test_user_login_wrong_password(self):
        """Test user login with wrong password"""
        self.assertFalse(auth_user("user", "456"))
    
    def test_nonexistent_user(self):
        """Test login with non-existent username"""
        self.assertFalse(auth_user("nonexistent", "123"))
    
    def test_empty_username(self):
        """Test login with empty username"""
        self.assertFalse(auth_user("", "123"))
    
    def test_empty_password(self):
        """Test login with empty password"""
        self.assertFalse(auth_user("admin", ""))
    
    def test_numeric_password_as_int(self):
        """Test password as integer (type conversion)"""
        self.assertTrue(auth_user("admin", 456))
        self.assertTrue(auth_user("user", 123))
    
    def test_case_sensitive_username(self):
        """Test that username is case sensitive"""
        self.assertFalse(auth_user("ADMIN", "456"))
        self.assertFalse(auth_user("Admin", "456"))
    
    def test_case_sensitive_password(self):
        """Test that password is case sensitive (if using string passwords)"""
        self.assertFalse(auth_user("admin", "456abc"))


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
