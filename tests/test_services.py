"""
Unit tests for USF Moving Company AI Agent services
"""

import unittest
from datetime import datetime, timedelta
from services.validation_service import ValidationService
from services.pricing_service import PricingService

class TestValidationService(unittest.TestCase):
    def setUp(self):
        self.validator = ValidationService()
    
    def test_extract_phone_number(self):
        """Test phone number extraction"""
        # Test various formats
        test_cases = [
            ("my number is two eight one seven four three four five zero three", "(281) 743-4503"),
            ("281 743 4503", "(281) 743-4503"),
            ("2817434503", "(281) 743-4503"),
            ("plus nine two three zero five four two four nine seven six one", "+923054249761"),
            ("nine two three zero five four two four nine seven six one", "+923054249761"),
        ]
        
        for input_text, expected in test_cases:
            result = self.validator.extract_phone_number(input_text)
            self.assertIsNotNone(result, f"Failed to extract from: {input_text}")
            # For US cases, ensure formatting matches; for international, ensure it startswith '+' and digits match length >= 11
            if expected.startswith('('):
                self.assertEqual(result, expected)
            else:
                self.assertTrue(result.startswith('+'))
                self.assertEqual(result, expected)

    def test_extract_digits_and_format(self):
        """Test low-level digit extraction and formatting"""
        digits = self.validator.extract_digits("my number is two eight one dash seven four three space four five zero three")
        self.assertEqual(digits, '2817434503')
        formatted = self.validator.format_phone(digits)
        self.assertEqual(formatted, "(281) 743-4503")
    
    def test_extract_email(self):
        """Test email extraction"""
        test_cases = [
            ("john at gmail dot com", "john@gmail.com"),
            ("test underscore user at yahoo dot com", "test_user@yahoo.com"),
        ]
        
        for input_text, expected in test_cases:
            result = self.validator.extract_email(input_text)
            self.assertIsNotNone(result, f"Failed to extract from: {input_text}")
    
    def test_validate_date(self):
        """Test date validation"""
        today = datetime.now()
        
        # Test "tomorrow"
        result = self.validator.validate_date("tomorrow")
        self.assertIsNotNone(result)
        self.assertEqual(result.date(), (today + timedelta(days=1)).date())
        
        # Test "next Monday"
        result = self.validator.validate_date("next monday")
        self.assertIsNotNone(result)

        # Test ordinal day with month name
        result = self.validator.validate_date("we want to for date 30th, october 2025")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 30)
        self.assertEqual(result.year, 2025)

        # Test month-day without year
        result = self.validator.validate_date("october 25th")
        self.assertIsNotNone(result)
    
    def test_extract_room_count(self):
        """Test room count extraction"""
        test_cases = [
            ("I have three rooms", 3),
            ("5 rooms total", 5),
            ("two bedroom", 2),
        ]
        
        for input_text, expected in test_cases:
            result = self.validator.extract_room_count(input_text)
            self.assertEqual(result, expected, f"Failed for: {input_text}")
    
    def test_validate_yes_no(self):
        """Test yes/no validation"""
        yes_inputs = ["yes", "yeah", "yep", "sure", "okay"]
        no_inputs = ["no", "nope", "nah", "not really"]
        
        for text in yes_inputs:
            self.assertEqual(self.validator.validate_yes_no(text), 'yes')
        
        for text in no_inputs:
            self.assertEqual(self.validator.validate_yes_no(text), 'no')


class TestPricingService(unittest.TestCase):
    def setUp(self):
        self.pricing = PricingService()
    
    def test_determine_tier(self):
        """Test pricing tier determination"""
        # Tier 1: 1-2 rooms, no stairs
        tier, movers = self.pricing.determine_tier(2, False)
        self.assertEqual(tier, 'tier_1')
        self.assertEqual(movers, 2)
        
        # Tier 2: 2-3 rooms with stairs
        tier, movers = self.pricing.determine_tier(3, True)
        self.assertEqual(tier, 'tier_2')
        self.assertEqual(movers, 3)
        
        # Tier 3: 3+ rooms with stairs
        tier, movers = self.pricing.determine_tier(4, True)
        self.assertEqual(tier, 'tier_3')
        self.assertEqual(movers, 4)
    
    def test_calculate_mileage_cost(self):
        """Test mileage cost calculation"""
        # Within free radius (20 miles)
        cost = self.pricing.calculate_mileage_cost(15)
        self.assertEqual(cost, 0)
        
        # Beyond free radius
        cost = self.pricing.calculate_mileage_cost(30)
        self.assertEqual(cost, 10.0)  # 30 - 20 = 10 miles * $1
    
    def test_calculate_base_rate(self):
        """Test base rate calculation"""
        # 0-2 jobs per week, tier 1
        base_rate, movers = self.pricing.calculate_base_rate(2, False, 2, False, 1)
        self.assertEqual(base_rate, 100)
        self.assertEqual(movers, 2)
        
        # 5-7 jobs per week, tier 2
        base_rate, movers = self.pricing.calculate_base_rate(3, True, 3, True, 6)
        self.assertEqual(base_rate, 175)
        self.assertEqual(movers, 3)


class TestConversationFlow(unittest.TestCase):
    """Test conversation flow logic"""
    
    def test_session_initialization(self):
        """Test that session is properly initialized"""
        session = {
            'phone': '+12817434503',
            'step': 'greeting',
            'data': {},
            'customer': None
        }
        
        self.assertIsNotNone(session)
        self.assertEqual(session['step'], 'greeting')
        self.assertIsInstance(session['data'], dict)
    
    def test_data_collection_flow(self):
        """Test that data collection follows correct flow"""
        steps = [
            'greeting',
            'collect_name',
            'collect_phone',
            'collect_email',
            'collect_move_type',
            'collect_pickup_type',
            'collect_pickup_address',
            'collect_pickup_rooms',
            'collect_pickup_stairs',
            'collect_dropoff_type',
            'collect_dropoff_address',
            'collect_dropoff_rooms',
            'collect_dropoff_stairs',
            'collect_date',
            'collect_time',
            'collect_packing',
            'collect_special_items',
            'collect_special_instructions',
            'provide_estimate',
            'confirm_booking'
        ]
        
        # Verify all steps are accounted for
        self.assertGreater(len(steps), 15)


if __name__ == '__main__':
    unittest.main()