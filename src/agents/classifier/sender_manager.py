"""
Sender Manager for MAE

Manages whitelist and blacklist of email senders and domains.
Supports wildcard matching.
"""

import re
import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


class SenderManager:
    """Manage sender and domain whitelist/blacklist"""
    
    def __init__(self, whitelisted: List[str], blacklisted: List[str],
                 agent_name: str = "unknown"):
        """
        Initialize sender manager
        
        Args:
            whitelisted: List of whitelisted senders/domains
            blacklisted: List of blacklisted senders/domains
            agent_name: Agent name for logging
        """
        self.agent_name = agent_name
        
        # Normalize and store lists
        self.whitelisted = self._normalize_list(whitelisted)
        self.blacklisted = self._normalize_list(blacklisted)
        
        logger.info(
            f"[{agent_name}] Loaded {len(self.whitelisted)} whitelisted "
            f"and {len(self.blacklisted)} blacklisted senders"
        )
    
    def _normalize_list(self, items: List[str]) -> Set[str]:
        """Normalize list of senders/domains to lowercase set"""
        return {item.lower().strip() for item in items if item.strip()}
    
    def is_whitelisted(self, email_address: str) -> bool:
        """
        Check if sender is whitelisted
        
        Args:
            email_address: Email address to check
        
        Returns:
            True if whitelisted
        """
        email_address = email_address.lower().strip()
        
        # Check exact match
        if email_address in self.whitelisted:
            logger.debug(f"[{self.agent_name}] {email_address} is whitelisted (exact)")
            return True
        
        # Check domain wildcard (e.g., *@example.com)
        domain = self._extract_domain(email_address)
        domain_wildcard = f"*@{domain}"
        
        if domain_wildcard in self.whitelisted:
            logger.debug(f"[{self.agent_name}] {email_address} is whitelisted (domain)")
            return True
        
        # Check partial wildcards (e.g., *example.com)
        for pattern in self.whitelisted:
            if '*' in pattern:
                if self._matches_wildcard(email_address, pattern):
                    logger.debug(
                        f"[{self.agent_name}] {email_address} is whitelisted "
                        f"(pattern: {pattern})"
                    )
                    return True
        
        return False
    
    def is_blacklisted(self, email_address: str) -> bool:
        """
        Check if sender is blacklisted
        
        Args:
            email_address: Email address to check
        
        Returns:
            True if blacklisted
        """
        email_address = email_address.lower().strip()
        
        # Check exact match
        if email_address in self.blacklisted:
            logger.debug(f"[{self.agent_name}] {email_address} is blacklisted (exact)")
            return True
        
        # Check domain wildcard
        domain = self._extract_domain(email_address)
        domain_wildcard = f"*@{domain}"
        
        if domain_wildcard in self.blacklisted:
            logger.debug(f"[{self.agent_name}] {email_address} is blacklisted (domain)")
            return True
        
        # Check partial wildcards
        for pattern in self.blacklisted:
            if '*' in pattern:
                if self._matches_wildcard(email_address, pattern):
                    logger.debug(
                        f"[{self.agent_name}] {email_address} is blacklisted "
                        f"(pattern: {pattern})"
                    )
                    return True
        
        return False
    
    def get_status(self, email_address: str) -> str:
        """
        Get sender status
        
        Args:
            email_address: Email address to check
        
        Returns:
            'whitelisted', 'blacklisted', or 'neutral'
        """
        # Whitelist takes priority over blacklist
        if self.is_whitelisted(email_address):
            return 'whitelisted'
        elif self.is_blacklisted(email_address):
            return 'blacklisted'
        else:
            return 'neutral'
    
    def _extract_domain(self, email_address: str) -> str:
        """
        Extract domain from email address
        
        Args:
            email_address: Email address
        
        Returns:
            Domain part
        """
        if '@' in email_address:
            return email_address.split('@')[1]
        return email_address
    
    def _matches_wildcard(self, email_address: str, pattern: str) -> bool:
        """
        Check if email matches wildcard pattern
        
        Args:
            email_address: Email address to check
            pattern: Wildcard pattern (e.g., *@example.com, user@*.com)
        
        Returns:
            True if matches
        """
        # Convert wildcard to regex
        # Escape special regex chars except *
        regex_pattern = re.escape(pattern).replace(r'\*', '.*')
        regex_pattern = f"^{regex_pattern}$"
        
        return bool(re.match(regex_pattern, email_address, re.IGNORECASE))
    
    def add_to_whitelist(self, email_or_domain: str):
        """
        Add sender/domain to whitelist
        
        Args:
            email_or_domain: Email address or domain pattern
        """
        normalized = email_or_domain.lower().strip()
        self.whitelisted.add(normalized)
        logger.info(f"[{self.agent_name}] Added to whitelist: {normalized}")
    
    def add_to_blacklist(self, email_or_domain: str):
        """
        Add sender/domain to blacklist
        
        Args:
            email_or_domain: Email address or domain pattern
        """
        normalized = email_or_domain.lower().strip()
        self.blacklisted.add(normalized)
        logger.info(f"[{self.agent_name}] Added to blacklist: {normalized}")
    
    def remove_from_whitelist(self, email_or_domain: str):
        """
        Remove sender/domain from whitelist
        
        Args:
            email_or_domain: Email address or domain pattern
        """
        normalized = email_or_domain.lower().strip()
        if normalized in self.whitelisted:
            self.whitelisted.remove(normalized)
            logger.info(f"[{self.agent_name}] Removed from whitelist: {normalized}")
    
    def remove_from_blacklist(self, email_or_domain: str):
        """
        Remove sender/domain from blacklist
        
        Args:
            email_or_domain: Email address or domain pattern
        """
        normalized = email_or_domain.lower().strip()
        if normalized in self.blacklisted:
            self.blacklisted.remove(normalized)
            logger.info(f"[{self.agent_name}] Removed from blacklist: {normalized}")
    
    def get_whitelist(self) -> List[str]:
        """Get whitelist as list"""
        return sorted(self.whitelisted)
    
    def get_blacklist(self) -> List[str]:
        """Get blacklist as list"""
        return sorted(self.blacklisted)


if __name__ == "__main__":
    # Test sender manager
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Create manager with test lists
    manager = SenderManager(
        whitelisted=[
            "important@example.com",
            "*@company.com",
            "noreply@github.com"
        ],
        blacklisted=[
            "spam@promotions.com",
            "*@marketing.example.com"
        ],
        agent_name="test"
    )
    
    # Test cases
    test_cases = [
        ("important@example.com", "whitelisted"),  # Exact match
        ("anyone@company.com", "whitelisted"),     # Domain wildcard
        ("noreply@github.com", "whitelisted"),     # Exact match
        ("spam@promotions.com", "blacklisted"),    # Exact match
        ("ads@marketing.example.com", "blacklisted"),  # Domain wildcard
        ("random@gmail.com", "neutral"),           # No match
    ]
    
    print("\n[Test] Checking sender statuses...")
    for email, expected in test_cases:
        status = manager.get_status(email)
        result = "✓" if status == expected else "✗"
        print(f"  {result} {email}: {status} (expected: {expected})")
        assert status == expected, f"Failed for {email}"
    
    # Test add/remove
    print("\n[Test] Add/remove operations...")
    manager.add_to_whitelist("newuser@test.com")
    assert manager.is_whitelisted("newuser@test.com")
    print("  ✓ Added to whitelist")
    
    manager.remove_from_whitelist("newuser@test.com")
    assert not manager.is_whitelisted("newuser@test.com")
    print("  ✓ Removed from whitelist")
    
    # Test wildcard matching
    print("\n[Test] Wildcard patterns...")
    manager.add_to_whitelist("*support@*.com")
    assert manager.is_whitelisted("techsupport@example.com")
    print("  ✓ Wildcard matching works")
    
    print("\n✓ All tests passed!")
