"""
Calendar Event Extractor for MAE

Extracts calendar events from email content using regex patterns.
Supports common date/time formats.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import calendar

logger = logging.getLogger(__name__)


class CalendarExtractor:
    """Extract calendar events from email content"""
    
    def __init__(self, agent_name: str = "unknown"):
        """
        Initialize calendar extractor
        
        Args:
            agent_name: Agent name for logging
        """
        self.agent_name = agent_name
        
        # Common event trigger words
        self.event_triggers = [
            'meeting', 'appointment', 'schedule', 'calendar',
            'conference', 'call', 'webinar', 'interview',
            'deadline', 'due', 'event', 'reminder'
        ]
        
        logger.info(f"[{agent_name}] Calendar extractor initialized")
    
    def extract_events(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract calendar events from email
        
        Args:
            email_data: Parsed email data
        
        Returns:
            List of extracted events, each with:
                - title: str
                - start_time: datetime
                - end_time: datetime (optional)
                - location: str (optional)
                - description: str
        """
        events = []
        
        subject = email_data.get('subject', '')
        body_text = email_data.get('body_text', '')
        
        # Check if email likely contains event info
        if not self._contains_event_trigger(subject + ' ' + body_text):
            logger.debug(f"[{self.agent_name}] No event triggers found in email")
            return events
        
        # Combine subject and body for extraction
        full_text = f"{subject}\n\n{body_text}"
        
        # Extract date/time patterns
        datetime_matches = self._extract_datetime_patterns(full_text)
        
        if not datetime_matches:
            logger.debug(f"[{self.agent_name}] No datetime patterns found")
            return events
        
        # Build events from matches
        for dt_info in datetime_matches:
            event = self._build_event(dt_info, email_data, full_text)
            if event:
                events.append(event)
        
        logger.info(
            f"[{self.agent_name}] Extracted {len(events)} event(s) from email {email_data.get('id')}"
        )
        
        return events
    
    def _contains_event_trigger(self, text: str) -> bool:
        """Check if text contains event trigger words"""
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in self.event_triggers)
    
    def _extract_datetime_patterns(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract datetime patterns from text
        
        Returns:
            List of datetime info dictionaries
        """
        matches = []
        
        # Pattern 1: "Meeting on Monday, Dec 25 at 3:00 PM"
        pattern1 = r'(?:on|at)\s+([A-Z][a-z]+,?\s+[A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)'
        for match in re.finditer(pattern1, text):
            date_str = match.group(1)
            time_str = match.group(2)
            combined = f"{date_str} {time_str}"
            
            try:
                dt = date_parser.parse(combined, fuzzy=True)
                matches.append({
                    'datetime': dt,
                    'context': match.group(0),
                    'type': 'explicit'
                })
            except Exception as e:
                logger.debug(f"[{self.agent_name}] Failed to parse: {combined}")
        
        # Pattern 2: "December 25, 2024 at 3:00 PM"
        pattern2 = r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)'
        for match in re.finditer(pattern2, text):
            date_str = match.group(1)
            time_str = match.group(2)
            combined = f"{date_str} {time_str}"
            
            try:
                dt = date_parser.parse(combined)
                matches.append({
                    'datetime': dt,
                    'context': match.group(0),
                    'type': 'explicit'
                })
            except Exception as e:
                logger.debug(f"[{self.agent_name}] Failed to parse: {combined}")
        
        # Pattern 3: "Tomorrow at 2:00 PM"
        pattern3 = r'(tomorrow|today)\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)'
        for match in re.finditer(pattern3, text, re.IGNORECASE):
            relative = match.group(1).lower()
            time_str = match.group(2)
            
            try:
                # Get base date
                if relative == 'today':
                    base_date = datetime.now().date()
                else:  # tomorrow
                    base_date = (datetime.now() + timedelta(days=1)).date()
                
                # Parse time
                time_obj = date_parser.parse(time_str).time()
                dt = datetime.combine(base_date, time_obj)
                
                matches.append({
                    'datetime': dt,
                    'context': match.group(0),
                    'type': 'relative'
                })
            except Exception as e:
                logger.debug(f"[{self.agent_name}] Failed to parse relative: {match.group(0)}")
        
        # Pattern 4: "Next Monday at 10:00 AM"
        pattern4 = r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)'
        for match in re.finditer(pattern4, text, re.IGNORECASE):
            day_name = match.group(1).lower()
            time_str = match.group(2)
            
            try:
                # Find next occurrence of the day
                dt = self._get_next_weekday(day_name, time_str)
                matches.append({
                    'datetime': dt,
                    'context': match.group(0),
                    'type': 'relative'
                })
            except Exception as e:
                logger.debug(f"[{self.agent_name}] Failed to parse weekday: {match.group(0)}")
        
        return matches
    
    def _get_next_weekday(self, day_name: str, time_str: str) -> datetime:
        """Get next occurrence of a weekday"""
        # Map day names to weekday numbers (0=Monday, 6=Sunday)
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        target_day = days[day_name.lower()]
        today = datetime.now()
        current_day = today.weekday()
        
        # Calculate days until next occurrence
        days_ahead = target_day - current_day
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_date = today + timedelta(days=days_ahead)
        
        # Parse time
        time_obj = date_parser.parse(time_str).time()
        
        return datetime.combine(next_date.date(), time_obj)
    
    def _build_event(self, dt_info: Dict[str, Any], 
                     email_data: Dict[str, Any],
                     full_text: str) -> Optional[Dict[str, Any]]:
        """
        Build event dictionary from datetime info
        
        Args:
            dt_info: Datetime info from extraction
            email_data: Original email data
            full_text: Full email text
        
        Returns:
            Event dictionary or None
        """
        try:
            start_time = dt_info['datetime']
            
            # Try to extract event title
            title = self._extract_event_title(dt_info['context'], full_text, email_data)
            
            # Try to extract location
            location = self._extract_location(full_text)
            
            # Default end time (1 hour after start)
            end_time = start_time + timedelta(hours=1)
            
            # Try to extract duration
            duration = self._extract_duration(full_text)
            if duration:
                end_time = start_time + duration
            
            event = {
                'title': title,
                'start_time': start_time,
                'end_time': end_time,
                'location': location,
                'description': f"Extracted from email: {email_data.get('subject', 'No Subject')}",
                'source_email_id': email_data.get('id'),
                'extraction_type': dt_info['type']
            }
            
            return event
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to build event: {e}")
            return None
    
    def _extract_event_title(self, context: str, full_text: str, 
                            email_data: Dict[str, Any]) -> str:
        """Extract event title from context"""
        # Try to find sentence containing the datetime
        sentences = re.split(r'[.!?\n]', full_text)
        for sentence in sentences:
            if context.lower() in sentence.lower():
                # Clean and use this sentence as title
                title = sentence.strip()
                if len(title) > 100:
                    title = title[:97] + '...'
                return title
        
        # Fallback to email subject
        subject = email_data.get('subject', 'Calendar Event')
        if len(subject) > 100:
            subject = subject[:97] + '...'
        return subject
    
    def _extract_location(self, text: str) -> str:
        """Extract location from text"""
        # Pattern: "Location: ..." or "at [location]"
        location_pattern = r'(?:location|venue|address|at):\s*([^\n,]+)'
        match = re.search(location_pattern, text, re.IGNORECASE)
        
        if match:
            location = match.group(1).strip()
            if len(location) > 200:
                location = location[:197] + '...'
            return location
        
        return ''
    
    def _extract_duration(self, text: str) -> Optional[timedelta]:
        """Extract event duration from text"""
        # Pattern: "for 2 hours", "30 minutes", "1.5 hours"
        duration_pattern = r'for\s+(\d+(?:\.\d+)?)\s+(hour|minute|hr|min)s?'
        match = re.search(duration_pattern, text, re.IGNORECASE)
        
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            
            if unit in ['hour', 'hr']:
                return timedelta(hours=value)
            elif unit in ['minute', 'min']:
                return timedelta(minutes=value)
        
        return None


if __name__ == "__main__":
    # Test calendar extractor
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    extractor = CalendarExtractor("test")
    
    # Test email 1: Explicit datetime
    email1 = {
        'id': 'email1',
        'subject': 'Team Meeting',
        'body_text': 'Meeting on Monday, Dec 25 at 3:00 PM in Conference Room A. Duration: 2 hours.'
    }
    
    print("\n[Test 1] Explicit datetime...")
    events1 = extractor.extract_events(email1)
    for event in events1:
        print(f"  Title: {event['title']}")
        print(f"  Start: {event['start_time']}")
        print(f"  End: {event['end_time']}")
        print(f"  Location: {event['location']}")
    
    # Test email 2: Relative datetime
    email2 = {
        'id': 'email2',
        'subject': 'Reminder: Call scheduled',
        'body_text': 'Your call with John is scheduled for tomorrow at 2:00 PM for 30 minutes.'
    }
    
    print("\n[Test 2] Relative datetime (tomorrow)...")
    events2 = extractor.extract_events(email2)
    for event in events2:
        print(f"  Title: {event['title']}")
        print(f"  Start: {event['start_time']}")
        print(f"  End: {event['end_time']}")
    
    # Test email 3: Next weekday
    email3 = {
        'id': 'email3',
        'subject': 'Interview Scheduled',
        'body_text': 'Your interview is next Monday at 10:00 AM. Location: Building 5, Room 301.'
    }
    
    print("\n[Test 3] Next weekday...")
    events3 = extractor.extract_events(email3)
    for event in events3:
        print(f"  Title: {event['title']}")
        print(f"  Start: {event['start_time']}")
        print(f"  Location: {event['location']}")
    
    # Test email 4: No event
    email4 = {
        'id': 'email4',
        'subject': 'New Product Launch',
        'body_text': 'Check out our new product features!'
    }
    
    print("\n[Test 4] No event (should be empty)...")
    events4 = extractor.extract_events(email4)
    print(f"  Events found: {len(events4)}")
    assert len(events4) == 0
    
    print("\n✓ All tests passed!")
