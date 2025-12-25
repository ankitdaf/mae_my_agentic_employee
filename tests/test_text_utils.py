import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.text_utils import sanitize_text

class TestTextUtils(unittest.TestCase):
    def test_sanitize_removes_newlines(self):
        text = "Line 1\nLine 2\r\nLine 3"
        sanitized = sanitize_text(text)
        self.assertEqual(sanitized, "Line 1 Line 2 Line 3")
        
    def test_sanitize_removes_tabs(self):
        text = "Col1\tCol2"
        sanitized = sanitize_text(text)
        self.assertEqual(sanitized, "Col1 Col2")
        
    def test_sanitize_collapses_spaces(self):
        text = "Word1    Word2"
        sanitized = sanitize_text(text)
        self.assertEqual(sanitized, "Word1 Word2")
        
    def test_sanitize_strips_whitespace(self):
        text = "  Hello World  "
        sanitized = sanitize_text(text)
        self.assertEqual(sanitized, "Hello World")
        
    def test_sanitize_handles_non_string(self):
        self.assertEqual(sanitize_text(123), "123")
        self.assertEqual(sanitize_text(None), "None")

if __name__ == '__main__':
    unittest.main()
