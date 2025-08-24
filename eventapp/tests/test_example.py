import unittest
from eventapp.dao import get_category_title, get_available_ticket_types, validate_ticket_availability

class DummyTicketType:
    def __init__(self, name, is_active, sold_quantity, total_quantity):
        self.name = name
        self.is_active = is_active
        self.sold_quantity = sold_quantity
        self.total_quantity = total_quantity

class TestDAO(unittest.TestCase):
    def test_get_category_title(self):
        self.assertEqual(get_category_title('music'), 'Âm Nhạc')
        self.assertEqual(get_category_title('sports'), 'Thể Thao')
        self.assertEqual(get_category_title('other'), 'Khác')
        self.assertEqual(get_category_title('unknown'), 'Unknown')

    def test_get_available_ticket_types(self):
        tickets = [
            DummyTicketType("VIP", True, 5, 10),
            DummyTicketType("Standard", True, 10, 10),
            DummyTicketType("Student", False, 0, 10),
        ]
        available = get_available_ticket_types(tickets)
        self.assertEqual(len(available), 1)
        self.assertEqual(available[0].name, "VIP")

    def test_validate_ticket_availability(self):
        # Giả lập TicketType.query.get trả về DummyTicketType
        import eventapp.dao
        old_query_get = eventapp.dao.TicketType.query.get

        class DummyQuery:
            def get(self, ticket_type_id):
                if ticket_type_id == 1:
                    return DummyTicketType("VIP", True, 5, 10)
                return None

        eventapp.dao.TicketType.query = DummyQuery()
        tickets_data = [{'ticket_type_id': 1, 'quantity': 3}]
        valid, msg = validate_ticket_availability(tickets_data)
        self.assertTrue(valid)
        tickets_data = [{'ticket_type_id': 1, 'quantity': 6}]
        valid, msg = validate_ticket_availability(tickets_data)
        self.assertFalse(valid)
        self.assertIn("Không đủ vé", msg)
        # Restore
        eventapp.dao.TicketType.query.get = old_query_get

if __name__ == '__main__':
    unittest.main()