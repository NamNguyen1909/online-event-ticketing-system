import unittest
from eventapp.dao import get_category_title

class TestDAO(unittest.TestCase):
    def test_get_category_title(self):
        self.assertEqual(get_category_title('music'), 'Âm Nhạc')
        self.assertEqual(get_category_title('sports'), 'Thể Thao')
        self.assertEqual(get_category_title('other'), 'Khác')
        self.assertEqual(get_category_title('unknown'), 'Unknown')

if __name__ == '__main__':
    unittest.main()