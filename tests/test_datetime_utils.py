import unittest
from datetime import datetime, timezone, timedelta
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.utils.datetime_utils import ensure_aware

class TestDatetimeUtils(unittest.TestCase):
    def test_ensure_aware_naive(self):
        dt = datetime(2023, 11, 20, 10, 0, 0)
        aware_dt = ensure_aware(dt)
        self.assertIsNotNone(aware_dt.tzinfo)
        self.assertEqual(aware_dt.tzinfo, timezone.utc)
        self.assertEqual(aware_dt.year, 2023)
        self.assertEqual(aware_dt.hour, 10)

    def test_ensure_aware_aware_utc(self):
        dt = datetime(2023, 11, 20, 10, 0, 0, tzinfo=timezone.utc)
        aware_dt = ensure_aware(dt)
        self.assertEqual(aware_dt.tzinfo, timezone.utc)
        self.assertEqual(aware_dt.hour, 10)

    def test_ensure_aware_aware_other(self):
        # UTC+5:30
        tz = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2023, 11, 20, 10, 0, 0, tzinfo=tz)
        aware_dt = ensure_aware(dt)
        self.assertEqual(aware_dt.tzinfo, timezone.utc)
        # 10:00 UTC+5:30 is 04:30 UTC
        self.assertEqual(aware_dt.hour, 4)
        self.assertEqual(aware_dt.minute, 30)

    def test_ensure_aware_none(self):
        self.assertIsNone(ensure_aware(None))

if __name__ == '__main__':
    unittest.main()
