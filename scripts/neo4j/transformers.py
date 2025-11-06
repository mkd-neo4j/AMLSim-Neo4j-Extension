"""
Data transformation utilities for converting AMLSim CSV data to Neo4j format
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Any


class DataTransformer:
    """
    Transforms AMLSim CSV data into Neo4j-compatible format
    """

    def __init__(self, base_date: datetime):
        """
        Initialize transformer with base date from conf.json

        Args:
            base_date: Simulation start date
        """
        self.base_date = base_date

    def days_to_datetime(self, days: Any) -> Optional[datetime]:
        """
        Convert AMLSim days (integer from base_date) to DateTime

        Args:
            days: Days from base_date (integer or string)

        Returns:
            DateTime object or None if special value (>= 1000000 means 'never')
        """
        try:
            num_days = int(days)
            if num_days >= 1000000:  # Special value for "never closes"
                return None
            return self.base_date + timedelta(days=num_days)
        except (ValueError, TypeError):
            return None

    def yyyymmdd_to_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Convert YYYYMMDD string to DateTime

        Args:
            date_str: Date string in YYYYMMDD format (e.g., "20170315")

        Returns:
            DateTime object or None if parsing fails
        """
        try:
            return datetime.strptime(str(date_str), "%Y%m%d")
        except (ValueError, TypeError):
            return None

    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parse datetime from various string formats

        Args:
            date_str: Date string in various formats (ISO 8601, YYYYMMDD, etc.)

        Returns:
            DateTime object or None if parsing fails
        """
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",       # ISO 8601 with Z: 2017-01-01T00:00:00Z
            "%Y-%m-%dT%H:%M:%S",        # ISO 8601: 2017-01-01T00:00:00
            "%Y-%m-%d %H:%M:%S",        # SQL datetime: 2017-01-01 00:00:00
            "%Y-%m-%d",                  # Date only: 2017-01-01
            "%Y%m%d",                    # Compact: 20170101
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except (ValueError, TypeError):
                continue

        return None

    def parse_boolean(self, value: Any) -> bool:
        """
        Parse boolean from string or other type

        Args:
            value: Value to parse (string, bool, int, etc.)

        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)

    def parse_float(self, value: Any) -> Optional[float]:
        """
        Parse float value safely

        Args:
            value: Value to parse

        Returns:
            Float value or None if parsing fails
        """
        try:
            return float(value) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None

    def parse_int(self, value: Any) -> Optional[int]:
        """
        Parse integer value safely

        Args:
            value: Value to parse

        Returns:
            Integer value or None if parsing fails
        """
        try:
            return int(value) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_address_key(street: str, city: str, postcode: str) -> str:
        """
        Generate normalized address key for deduplication

        Normalization process:
        1. Combine address parts
        2. Lowercase all text
        3. Remove special characters (keep only alphanumeric and spaces)
        4. Collapse multiple spaces to one
        5. Generate SHA-256 hash

        Args:
            street: Street address
            city: City name
            postcode: Postal code

        Returns:
            SHA-256 hash of normalized address (hex string)
        """
        # Combine address parts
        combined = f"{street} {city} {postcode}"

        # Lowercase and remove special chars
        normalized = re.sub(r'[^a-z0-9\s]', '', combined.lower())

        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized.strip())

        # Generate hash
        return hashlib.sha256(normalized.encode()).hexdigest()

# ISO 3166-1 alpha-2 country code lookup table
COUNTRY_CODES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "JP": "Japan",
    "CN": "China",
    "IN": "India",
    "BR": "Brazil",
    "MX": "Mexico",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "SG": "Singapore",
    "HK": "Hong Kong",
    "KR": "South Korea",
    "SE": "Sweden",
    "NO": "Norway",
}


def get_country_name(code: str) -> str:
    """
    Get country name from ISO 3166-1 alpha-2 code

    Args:
        code: Two-letter country code

    Returns:
        Country name or the code itself if not found
    """
    return COUNTRY_CODES.get(code.upper(), code)
