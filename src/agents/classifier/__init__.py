"""Classifier module initialization"""

from .classifier import EmailClassifier, ClassificationError
from .topic_matcher import TopicMatcher
from .sender_manager import SenderManager

__all__ = [
    'EmailClassifier',
    'ClassificationError',
    'TopicMatcher',
    'SenderManager'
]
