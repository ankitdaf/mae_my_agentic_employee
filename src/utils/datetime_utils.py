"""
Datetime utilities for MAE.
"""

from datetime import datetime, timezone
from typing import Optional

def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime object is timezone-aware (UTC).
    
    Args:
        dt: Datetime object (can be naive or aware)
        
    Returns:
        Timezone-aware datetime object in UTC, or None if input is None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Assume naive datetimes are UTC
        return dt.replace(tzinfo=timezone.utc)
    
    # Convert aware datetimes to UTC
    return dt.astimezone(timezone.utc)
