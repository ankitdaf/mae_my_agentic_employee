#!/usr/bin/env python3
"""
Test email classification with new 4-category system

Tests the classifier with sample emails for each category.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.classifier import EmailClassifier

def test_classification():
    """Test classification with sample emails"""
    
    print("=" * 70)
    print("Email Classification Test - 4 Categories")
    print("=" * 70)
    
    # Initialize classifier (rule-based)
    classifier = EmailClassifier(
        model_path=None,
        use_model=False,
        agent_name="test"
    )
    
    # Test emails for each category
    test_cases = [
        {
            'name': 'Transaction - Invoice',
            'email': {
                'subject': 'Your invoice from Amazon',
                'body_text': 'Thank you for your purchase. Your order has been charged to your card.',
                'from_email': 'no-reply@amazon.com'
            },
            'expected': 'transactions'
        },
        {
            'name': 'Transaction - Stock Trade',
            'email': {
                'subject': 'Trade Confirmation - AAPL',
                'body_text': 'Your stock trade has been executed. 10 shares of AAPL purchased.',
                'from_email': 'alerts@zerodha.com'
            },
            'expected': 'transactions'
        },
        {
            'name': 'Feed - Newsletter',
            'email': {
                'subject': 'Weekly Tech Digest',
                'body_text': 'Here are this week\'s top tech stories. Unsubscribe anytime.',
                'from_email': 'newsletter@techcrunch.com'
            },
            'expected': 'feed'
        },
        {
            'name': 'Feed - Tutorial',
            'email': {
                'subject': 'New Python Tutorial: Async Programming',
                'body_text': 'Learn async programming in Python. New article published today.',
                'from_email': 'updates@medium.com'
            },
            'expected': 'feed'
        },
        {
            'name': 'Promotions - Sale',
            'email': {
                'subject': '50% OFF - Limited Time Offer!',
                'body_text': 'Huge sale! Save 50% on all items. Buy now before it\'s too late!',
                'from_email': 'marketing@store.com'
            },
            'expected': 'promotions'
        },
        {
            'name': 'Promotions - Discount',
            'email': {
                'subject': 'Exclusive Deal Just For You',
                'body_text': 'Get 30% discount with code SAVE30. Shop now!',
                'from_email': 'offers@shop.com'
            },
            'expected': 'promotions'
        },
        {
            'name': 'Inbox - Personal',
            'email': {
                'subject': 'Re: Meeting tomorrow',
                'body_text': 'Sure, let\'s meet at 3pm. See you then!',
                'from_email': 'friend@gmail.com'
            },
            'expected': 'inbox'
        },
        {
            'name': 'Inbox - Work',
            'email': {
                'subject': 'Project Update',
                'body_text': 'Here\'s the latest update on the project. Let me know your thoughts.',
                'from_email': 'colleague@company.com'
            },
            'expected': 'inbox'
        }
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n[Test] {test['name']}")
        print(f"  Subject: {test['email']['subject']}")
        
        result = classifier.classify(test['email'])
        
        category = result['category']
        confidence = result['confidence']
        scores = result.get('scores', {})
        
        # Check if classification matches expected
        if category == test['expected']:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        print(f"  Expected: {test['expected']}")
        print(f"  Got: {category} (confidence: {confidence:.2f}) {status}")
        print(f"  Scores: {scores}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Passed: {passed}/{len(test_cases)}")
    print(f"Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(test_classification())
