"""
Email Deleter for MAE

Implements smart email deletion/labeling based on classification and sender lists.
Includes dry-run mode for testing.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailDeleter:
    """Smart email deletion/labeling with configurable rules"""
    
    def __init__(self, config: Dict[str, Any], agent_name: str = "unknown"):
        """
        Initialize email deleter
        
        Args:
            config: Deletion configuration from agent config
            agent_name: Agent name for logging
        """
        self.agent_name = agent_name
        
        # Load configuration
        self.action_on_deletion = config.get('action_on_deletion', 'move_to_trash')
        # Only promotions emails can be deleted - important/normal are preserved
        self.delete_promotional = config.get('delete_promotional', True)
        self.dry_run = config.get('dry_run', True)
        
        logger.info(
            f"[{agent_name}] Email deleter initialized "
            f"(action={self.action_on_deletion}, dry_run={self.dry_run})"
        )
        
        if self.dry_run:
            logger.warning(f"[{agent_name}] Running in DRY-RUN mode (no actual actions)")
    
    def should_act(self, email_data: Dict[str, Any],
                      classification: Dict[str, Any],
                      topic_match: Dict[str, Any],
                      sender_status: str) -> Dict[str, Any]:
        """
        Determine if an action should be taken on an email
        
        Args:
            email_data: Parsed email data
            classification: Classification result from classifier
            topic_match: Topic match result from topic matcher
            sender_status: Sender status from sender manager
        
        Returns:
            Decision dictionary:
                - should_act: bool
                - action: str ('move_to_trash', 'apply_label', 'none')
                - reason: str (explanation)
                - confidence: float (0-1)
        """
        # Never act on whitelisted senders
        if sender_status == 'whitelisted':
            return {
                'should_act': False,
                'action': 'none',
                'reason': 'Sender is whitelisted',
                'confidence': 1.0
           }
        
        # Always act on blacklisted senders - highest priority
        if sender_status == 'blacklisted':
            return {
                'should_act': True,
                'action': self.action_on_deletion,
                'reason': 'Sender is blacklisted',
                'confidence': 1.0
            }
        
        # Get category
        category = classification.get('category', 'normal')
        
        # ONLY promotional emails can be acted upon - important/normal are always preserved
        if category != 'promotions':
            return {
                'should_act': False,
                'action': 'none',
                'reason': f'Only promotional emails are targeted, "{category}" emails are preserved',
                'confidence': 1.0
            }
        
        # For promotions emails, check if deletion/action is enabled
        if not self.delete_promotional:
            return {
                'should_act': False,
                'action': 'none',
                'reason': 'Promotional email action is disabled',
                'confidence': 1.0
            }
        
        # Don't act on promotions emails if they match topics of interest
        if topic_match.get('matched', False):
            # Only skip if the match is strong enough (e.g. in subject or multiple times in body)
            # A single mention in the body (score 0.5, normalized 0.05) is often a false positive
            topic_score = topic_match.get('score', 0)
            if topic_score >= 0.15: # Equivalent to 1.5 raw score (e.g. 3 mentions in body or 1 in subject)
                return {
                    'should_act': False,
                    'action': 'none',
                    'reason': f'Promotional but matches topics: {topic_match["topics"]} (score: {topic_score:.2f})',
                    'confidence': 1.0
                }
            else:
                logger.info(
                    f"[{self.agent_name}] Weak topic match for '{category}' email "
                    f"(score: {topic_score:.2f}), proceeding with deletion"
                )
        
        # Email meets criteria
        return {
            'should_act': True,
            'action': self.action_on_deletion,
            'reason': f'Category "{category}" email met criteria',
            'confidence': classification.get('confidence', 0.8)
        }


if __name__ == "__main__":
    # Test email deleter
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Create deleter with test config
    config = {
        'action_on_deletion': 'move_to_trash',
        'delete_promotional': True,
        'dry_run': True
    }
    
    deleter = EmailDeleter(config, "test")
    
    # Test case 1: Promotions (should act)
    email1 = {
        'id': '123',
        'subject': 'Sale Email'
    }
    classification1 = {'category': 'promotions', 'confidence': 0.9}
    topic_match1 = {'matched': False}
    sender_status1 = 'neutral'
    
    print("\n[Test 1] Promotional email...")
    decision1 = deleter.should_act(email1, classification1, topic_match1, sender_status1)
    print(f"  Should act: {decision1['should_act']}")
    print(f"  Action: {decision1['action']}")
    print(f"  Reason: {decision1['reason']}")
    assert decision1['should_act'] == True
    assert decision1['action'] == 'move_to_trash'
    
    # Test case 2: Promotions but matches topic (should NOT act)
    email2 = {
        'id': '124',
        'subject': 'ML Course Sale'
    }
    classification2 = {'category': 'promotions', 'confidence': 0.9}
    topic_match2 = {'matched': True, 'topics': ['machine learning']}
    sender_status2 = 'neutral'
    
    print("\n[Test 2] Promotional but matches topic...")
    decision2 = deleter.should_act(email2, classification2, topic_match2, sender_status2)
    print(f"  Should act: {decision2['should_act']}")
    print(f"  Reason: {decision2['reason']}")
    assert decision2['should_act'] == False
    
    # Test case 3: Whitelisted sender (should NOT act)
    email3 = {
        'id': '125',
        'subject': 'Old Email'
    }
    classification3 = {'category': 'promotions', 'confidence': 0.9}
    topic_match3 = {'matched': False}
    sender_status3 = 'whitelisted'
    
    print("\n[Test 3] Whitelisted sender...")
    decision3 = deleter.should_act(email3, classification3, topic_match3, sender_status3)
    print(f"  Should act: {decision3['should_act']}")
    print(f"  Reason: {decision3['reason']}")
    assert decision3['should_act'] == False
    
    # Test case 4: Blacklisted sender (should act)
    email5 = {
        'id': '127',
        'subject': 'Spam'
    }
    classification5 = {'category': 'normal', 'confidence': 0.7}
    topic_match5 = {'matched': False}
    sender_status5 = 'blacklisted'
    
    print("\n[Test 4] Blacklisted sender...")
    decision5 = deleter.should_act(email5, classification5, topic_match5, sender_status5)
    print(f"  Should act: {decision5['should_act']}")
    print(f"  Action: {decision5['action']}")
    print(f"  Reason: {decision5['reason']}")
    assert decision5['should_act'] == True
    
    print("\n✓ All tests passed!")
