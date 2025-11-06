"""
Unit tests for data transformation utilities
"""

import unittest
from datetime import datetime, timedelta
import sys
import os

# Add scripts/neo4j to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../scripts/neo4j'))

from transformers import DataTransformer, get_country_name


class TestDataTransformer(unittest.TestCase):
    """
    Test suite for DataTransformer class
    """

    def setUp(self):
        """
        Set up test fixtures
        """
        self.base_date = datetime(2017, 1, 1)
        self.transformer = DataTransformer(self.base_date)

    def test_days_to_datetime_valid(self):
        """
        Test conversion of valid days to datetime
        """
        # Day 0 should be base_date
        result = self.transformer.days_to_datetime(0)
        self.assertEqual(result, self.base_date)

        # Day 10 should be 10 days after base_date
        result = self.transformer.days_to_datetime(10)
        expected = self.base_date + timedelta(days=10)
        self.assertEqual(result, expected)

        # Day 365 should be 1 year after base_date
        result = self.transformer.days_to_datetime(365)
        expected = self.base_date + timedelta(days=365)
        self.assertEqual(result, expected)

    def test_days_to_datetime_special_values(self):
        """
        Test special values (>= 1000000 means 'never')
        """
        result = self.transformer.days_to_datetime(1000000)
        self.assertIsNone(result)

        result = self.transformer.days_to_datetime(9999999)
        self.assertIsNone(result)

    def test_days_to_datetime_invalid(self):
        """
        Test invalid input handling
        """
        result = self.transformer.days_to_datetime(None)
        self.assertIsNone(result)

        result = self.transformer.days_to_datetime("invalid")
        self.assertIsNone(result)

    def test_yyyymmdd_to_datetime_valid(self):
        """
        Test conversion of YYYYMMDD strings to datetime
        """
        result = self.transformer.yyyymmdd_to_datetime("20170101")
        expected = datetime(2017, 1, 1)
        self.assertEqual(result, expected)

        result = self.transformer.yyyymmdd_to_datetime("20171231")
        expected = datetime(2017, 12, 31)
        self.assertEqual(result, expected)

    def test_yyyymmdd_to_datetime_invalid(self):
        """
        Test invalid date string handling
        """
        result = self.transformer.yyyymmdd_to_datetime("invalid")
        self.assertIsNone(result)

        result = self.transformer.yyyymmdd_to_datetime(None)
        self.assertIsNone(result)

        result = self.transformer.yyyymmdd_to_datetime("2017-01-01")  # Wrong format
        self.assertIsNone(result)

    def test_parse_boolean_from_string(self):
        """
        Test boolean parsing from strings
        """
        self.assertTrue(self.transformer.parse_boolean("true"))
        self.assertTrue(self.transformer.parse_boolean("True"))
        self.assertTrue(self.transformer.parse_boolean("TRUE"))
        self.assertTrue(self.transformer.parse_boolean("  true  "))

        self.assertFalse(self.transformer.parse_boolean("false"))
        self.assertFalse(self.transformer.parse_boolean("False"))
        self.assertFalse(self.transformer.parse_boolean("FALSE"))
        self.assertFalse(self.transformer.parse_boolean("anything"))
        self.assertFalse(self.transformer.parse_boolean(""))

    def test_parse_boolean_from_bool(self):
        """
        Test boolean parsing from actual boolean values
        """
        self.assertTrue(self.transformer.parse_boolean(True))
        self.assertFalse(self.transformer.parse_boolean(False))

    def test_parse_float_valid(self):
        """
        Test float parsing with valid inputs
        """
        self.assertEqual(self.transformer.parse_float("123.45"), 123.45)
        self.assertEqual(self.transformer.parse_float("100"), 100.0)
        self.assertEqual(self.transformer.parse_float(99.99), 99.99)
        self.assertEqual(self.transformer.parse_float("-50.5"), -50.5)

    def test_parse_float_invalid(self):
        """
        Test float parsing with invalid inputs
        """
        self.assertIsNone(self.transformer.parse_float(None))
        self.assertIsNone(self.transformer.parse_float(""))
        self.assertIsNone(self.transformer.parse_float("  "))
        self.assertIsNone(self.transformer.parse_float("invalid"))

    def test_parse_int_valid(self):
        """
        Test integer parsing with valid inputs
        """
        self.assertEqual(self.transformer.parse_int("123"), 123)
        self.assertEqual(self.transformer.parse_int(456), 456)
        self.assertEqual(self.transformer.parse_int("-10"), -10)

    def test_parse_int_invalid(self):
        """
        Test integer parsing with invalid inputs
        """
        self.assertIsNone(self.transformer.parse_int(None))
        self.assertIsNone(self.transformer.parse_int(""))
        self.assertIsNone(self.transformer.parse_int("  "))
        self.assertIsNone(self.transformer.parse_int("12.5"))
        self.assertIsNone(self.transformer.parse_int("invalid"))

    def test_normalize_address_key(self):
        """
        Test address normalization for deduplication
        """
        # Same address with different formatting should produce same hash
        hash1 = DataTransformer.normalize_address_key("123 Main St", "New York", "10001")
        hash2 = DataTransformer.normalize_address_key("123 MAIN ST", "New York", "10001")
        hash3 = DataTransformer.normalize_address_key("123  Main  St", "new york", "10001")

        self.assertEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)

        # Different addresses should produce different hashes
        hash4 = DataTransformer.normalize_address_key("456 Oak Ave", "New York", "10001")
        self.assertNotEqual(hash1, hash4)

        # Hash should be SHA-256 hex (64 characters)
        self.assertEqual(len(hash1), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))


class TestCountryCodeLookup(unittest.TestCase):
    """
    Test suite for country code lookup
    """

    def test_get_country_name_valid(self):
        """
        Test getting country names from valid codes
        """
        self.assertEqual(get_country_name("US"), "United States")
        self.assertEqual(get_country_name("GB"), "United Kingdom")
        self.assertEqual(get_country_name("JP"), "Japan")

        # Case insensitive
        self.assertEqual(get_country_name("us"), "United States")
        self.assertEqual(get_country_name("Gb"), "United Kingdom")

    def test_get_country_name_invalid(self):
        """
        Test getting country names from invalid codes (returns code itself)
        """
        self.assertEqual(get_country_name("XX"), "XX")
        self.assertEqual(get_country_name("ZZZ"), "ZZZ")


if __name__ == '__main__':
    unittest.main()
