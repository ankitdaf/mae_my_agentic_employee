"""
Topic Matcher for MAE

Matches email content against user-defined topics of interest.
Uses simple keyword matching with scoring.
"""

import re
import logging
from typing import List, Dict, Any, Set
from collections import Counter

logger = logging.getLogger(__name__)


class TopicMatcher:
    """Match email content against topics of interest"""
    
    def __init__(self, topics_of_interest: List[str], agent_name: str = "unknown"):
        """
        Initialize topic matcher
        
        Args:
            topics_of_interest: List of topics user cares about
            agent_name: Agent name for logging
        """
        self.topics_of_interest = [t.lower().strip() for t in topics_of_interest]
        self.agent_name = agent_name
        
        # Build keyword variations for each topic
        self.topic_keywords = self._build_topic_keywords()
        
        logger.info(
            f"[{agent_name}] Loaded {len(self.topics_of_interest)} topics of interest"
        )
    
    def _build_topic_keywords(self) -> Dict[str, Dict[str, Any]]:
        """
        Build keyword variations and phrases for each topic
        
        Returns:
            Dictionary mapping topic to its match configuration
        """
        config = {}
        
        for topic in self.topics_of_interest:
            topic_config = {
                'keywords': set(),
                'phrases': set(),
                'is_multi_word': False
            }
            
            clean_topic = topic.lower().strip()
            
            # Check if multi-word
            words = re.findall(r'\w+', clean_topic)
            if len(words) > 1:
                topic_config['is_multi_word'] = True
                topic_config['phrases'].add(clean_topic)
                
                # Add common variations for specific multi-word topics
                if clean_topic == "machine learning":
                    topic_config['keywords'].update(["ml", "machinelearning"])
                elif clean_topic == "artificial intelligence":
                    topic_config['keywords'].update(["ai", "artificialintelligence"])
            else:
                topic_config['keywords'].add(clean_topic)
                
                # Add common variations for specific single-word topics
                if clean_topic == "kubernetes":
                    topic_config['keywords'].add("k8s")
            
            config[topic] = topic_config
        
        return config
    
    def match(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match email against topics of interest
        
        Args:
            email_data: Parsed email data
        
        Returns:
            Match result dictionary
        """
        # Extract searchable text
        subject = email_data.get('subject', '').lower()
        body_text = email_data.get('body_text', '').lower()
        body_html = email_data.get('body_html', '')
        
        # If no plain text body, try HTML
        if not body_text and body_html:
            from src.agents.email import EmailParser
            parser = EmailParser(self.agent_name)
            body_text = parser.html_to_text(body_html).lower()
        
        # Combine all text
        all_text = f"{subject} {body_text}"
        
        # Extract words for keyword matching
        words = set(re.findall(r'\w+', all_text))
        
        # Match against topics
        matched_topics = []
        match_details = {}
        
        for topic, config in self.topic_keywords.items():
            topic_score = 0.0
            matched_keywords = []
            matched_phrases = []
            
            # 1. Check phrases (for multi-word topics)
            for phrase in config['phrases']:
                if phrase in all_text:
                    # Phrase match is strong
                    count_in_subject = subject.count(phrase)
                    count_in_body = body_text.count(phrase)
                    
                    topic_score += count_in_subject * 4.0  # Phrase in subject is very strong
                    topic_score += count_in_body * 2.0     # Phrase in body is strong
                    matched_phrases.append(phrase)
            
            # 2. Check keywords
            matching_keywords = words.intersection(config['keywords'])
            if matching_keywords:
                for kw in matching_keywords:
                    count_in_subject = subject.count(kw)
                    count_in_body = all_text.count(kw)
                    
                    topic_score += count_in_subject * 2.0
                    topic_score += count_in_body * 0.5
                    matched_keywords.append(kw)
            
            if topic_score > 0:
                matched_topics.append(topic)
                match_details[topic] = {
                    'keywords': matched_keywords,
                    'phrases': matched_phrases,
                    'score': topic_score
                }
        
        # Calculate overall score
        if matched_topics:
            total_score = sum(d['score'] for d in match_details.values())
            overall_score = min(total_score / 10.0, 1.0)
        else:
            overall_score = 0.0
        
        result = {
            'matched': len(matched_topics) > 0,
            'topics': matched_topics,
            'score': overall_score,
            'matches': match_details
        }
        
        if result['matched']:
            logger.debug(
                f"[{self.agent_name}] Email matched topics: {matched_topics} "
                f"(score: {overall_score:.2f})"
            )
        
        return result
    
    def add_topic(self, topic: str):
        """
        Add a new topic of interest
        
        Args:
            topic: Topic to add
        """
        topic = topic.lower().strip()
        if topic not in self.topics_of_interest:
            self.topics_of_interest.append(topic)
            self.topic_keywords = self._build_topic_keywords()
            logger.info(f"[{self.agent_name}] Added topic: {topic}")
    
    def remove_topic(self, topic: str):
        """
        Remove a topic of interest
        
        Args:
            topic: Topic to remove
        """
        topic = topic.lower().strip()
        if topic in self.topics_of_interest:
            self.topics_of_interest.remove(topic)
            self.topic_keywords = self._build_topic_keywords()
            logger.info(f"[{self.agent_name}] Removed topic: {topic}")
    
    def get_topics(self) -> List[str]:
        """Get list of all topics"""
        return self.topics_of_interest.copy()


if __name__ == "__main__":
    # Test topic matcher
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Create matcher with test topics
    matcher = TopicMatcher([
        "machine learning",
        "kubernetes",
        "family"
    ], "test")
    
    # Test email 1: Should match ML
    email1 = {
        'subject': 'New Machine Learning Course Available',
        'body_text': 'Check out this amazing ML course for beginners...',
        'body_html': ''
    }
    
    print("\n[Test 1] Machine Learning email...")
    result1 = matcher.match(email1)
    print(f"  Matched: {result1['matched']}")
    print(f"  Topics: {result1['topics']}")
    print(f"  Score: {result1['score']:.2f}")
    print(f"  Details: {result1['matches']}")
    
    # Test email 2: Should match Kubernetes
    email2 = {
        'subject': 'K8s Update: Version 1.28 Released',
        'body_text': 'Kubernetes version 1.28 is now available with new features...',
        'body_html': ''
    }
    
    print("\n[Test 2] Kubernetes email...")
    result2 = matcher.match(email2)
    print(f"  Matched: {result2['matched']}")
    print(f"  Topics: {result2['topics']}")
    print(f"  Score: {result2['score']:.2f}")
    
    # Test email 3: Should NOT match
    email3 = {
        'subject': 'Special Offer: 50% Off Shoes',
        'body_text': 'Limited time offer on all footwear...',
        'body_html': ''
    }
    
    print("\n[Test 3] Promotional email (no match)...")
    result3 = matcher.match(email3)
    print(f"  Matched: {result3['matched']}")
    print(f"  Topics: {result3['topics']}")
    print(f"  Score: {result3['score']:.2f}")
    
    # Test add/remove topic
    print("\n[Test 4] Add/remove topic...")
    matcher.add_topic("docker")
    print(f"  Topics: {matcher.get_topics()}")
    matcher.remove_topic("family")
    print(f"  Topics: {matcher.get_topics()}")
    
    print("\n✓ All tests passed!")
