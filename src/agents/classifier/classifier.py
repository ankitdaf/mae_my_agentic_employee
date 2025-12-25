"""
Email Classifier for MAE

Classifies emails into 4 categories using MobileBERT model (RKNN) or rule-based fallback:
- Transactions: Bills, payments, stock trades
- Feed: Newsletters, tutorials, announcements
- Promotions: Sales, offers, marketing
- Inbox: Personal/work emails (default)
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import re
from src.utils.text_utils import sanitize_text

logger = logging.getLogger(__name__)


class ClassificationError(Exception):
    """Raised when classification fails"""
    pass


class EmailClassifier:
    """Classify emails using AI model or fallback rules"""
    
    CATEGORIES = ['transactions', 'feed', 'promotions', 'inbox']
    
    def __init__(self, model_path: Optional[Path] = None, 
                 tokenizer_path: Optional[Path] = None,
                 use_model: bool = True, agent_name: str = "unknown",
                 debug_log_path: Optional[Path] = None):
        """
        Initialize email classifier
        
        Args:
            model_path: Path to RKNN model file
            tokenizer_path: Path to HuggingFace tokenizer directory
            use_model: Whether to use AI model (True) or fallback rules (False)
            agent_name: Agent name for logging
        """
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.use_model = use_model and model_path and model_path.exists()
        self.agent_name = agent_name
        self.debug_log_path = debug_log_path
        self.model = None
        self.model_type = None  # 'rknn' or 'onnx'
        self.tokenizer = None
        
        # Initialize debug log
        if self.debug_log_path:
            self._init_debug_log()
        self.max_length = 384  # Max sequence length for concatenated inputs
        
        if self.use_model:
            self._load_model()
            self._load_tokenizer()
        else:
            logger.warning(
                f"[{agent_name}] AI model not available, using fallback rule-based classification"
            )
    
    def _load_model(self):
        """
        Load RKNN model or fallback to ONNX
        """
        # Try loading RKNN first
        try:
            from rknnlite.api import RKNNLite
            
            logger.info(f"[{self.agent_name}] Loading RKNN model from {self.model_path}")
            
            self.model = RKNNLite()
            ret = self.model.load_rknn(str(self.model_path))
            if ret != 0:
                raise ClassificationError(f"Failed to load RKNN model: {ret}")
            
            ret = self.model.init_runtime()
            if ret != 0:
                raise ClassificationError(f"Failed to init RKNN runtime: {ret}")
            
            logger.info(f"[{self.agent_name}] RKNN model loaded successfully")
            self.use_model = True
            self.model_type = 'rknn'
            return
        
        except (ImportError, Exception) as e:
            logger.warning(f"[{self.agent_name}] RKNN load failed: {e}")
            
        # Fallback to ONNX
        try:
            import onnxruntime as ort
            
            # Check for ONNX model file (assume same name but .onnx extension)
            onnx_path = self.model_path.with_suffix('.onnx')
            if not onnx_path.exists():
                logger.warning(f"[{self.agent_name}] ONNX model not found at {onnx_path}")
                self.use_model = False
                return

            logger.info(f"[{self.agent_name}] Loading ONNX model from {onnx_path}")
            self.model = ort.InferenceSession(str(onnx_path))
            self.use_model = True
            self.model_type = 'onnx'
            logger.info(f"[{self.agent_name}] ONNX model loaded successfully")
            
        except ImportError:
            logger.warning(f"[{self.agent_name}] onnxruntime not found. Install with: pip install onnxruntime")
            self.use_model = False
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to load ONNX model: {e}")
            self.use_model = False
    
    def _load_tokenizer(self):
        """
        Load HuggingFace tokenizer
        
        Note: This requires transformers library to be installed
        """
        if not self.tokenizer_path or not Path(self.tokenizer_path).exists():
            logger.warning(
                f"[{self.agent_name}] Tokenizer path not found: {self.tokenizer_path}, "
                f"using fallback classification"
            )
            self.use_model = False
            return
        
        try:
            from transformers import AutoTokenizer
            
            logger.info(f"[{self.agent_name}] Loading tokenizer from {self.tokenizer_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.tokenizer_path))
            logger.info(f"[{self.agent_name}] Tokenizer loaded successfully")
        
        except ImportError:
            logger.warning(
                f"[{self.agent_name}] transformers library not found, "
                f"using fallback classification. Install with: pip install transformers"
            )
            self.use_model = False
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to load tokenizer: {e}")
            self.use_model = False
    
    def classify(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify email
        
        Args:
            email_data: Parsed email data
        
        Returns:
            Classification result:
                - category: 'transactions', 'feed', 'promotions', or 'inbox'
                - confidence: 0.0-1.0
                - method: 'model' or 'rules'
        """
        if self.use_model and self.model:
            if self.model_type == 'rknn':
                return self._classify_with_rknn(email_data)
            elif self.model_type == 'onnx':
                return self._classify_with_onnx(email_data)
        
        return self._classify_with_rules(email_data)

    def _init_debug_log(self):
        """Initialize debug log CSV"""
        import csv
        if not self.debug_log_path.exists():
            with open(self.debug_log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'input_string', 'category', 'confidence', 'method'])

    def _log_debug_info(self, input_string: str, result: Dict[str, Any]):
        """Log classification debug info"""
        if not self.debug_log_path:
            return
            
        try:
            import csv
            from datetime import datetime
            
            with open(self.debug_log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    input_string,
                    result['category'],
                    result['confidence'],
                    result['method']
                ])
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to log debug info: {e}")
    
    def _classify_with_rknn(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify using MobileBERT RKNN model on NPU
        
        Uses concatenation with special separators:
        [SUBJECT] {subject} [SENDER] {sender} [BODY] {body}
        
        Args:
            email_data: Parsed email data
        
        Returns:
            Classification result
        """
        try:
            import numpy as np
            
            # Prepare concatenated input with special separators
            input_text = self._prepare_model_input(email_data)
            
            # Tokenize text using HuggingFace tokenizer
            input_ids, attention_mask = self._tokenize_text(input_text)
            
            # Run inference on NPU
            outputs = self.model.inference(inputs=[input_ids, attention_mask])
            
            # Parse outputs (4 classes: transactions=0, feed=1, promotions=2, inbox=3)
            logits = outputs[0][0]  # Shape: (4,)
            
            # Apply softmax to get probabilities
            exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
            probs = exp_logits / np.sum(exp_logits)
            
            # Get predicted class
            predicted_class = int(np.argmax(probs))
            confidence = float(probs[predicted_class])
            
            # Map class index to category
            class_names = ['transactions', 'feed', 'promotions', 'inbox']
            category = class_names[predicted_class]
            
            result = {
                'category': category,
                'confidence': confidence,
                'method': 'model',
                'probabilities': {
                    'transactions': float(probs[0]),
                    'feed': float(probs[1]),
                    'promotions': float(probs[2]),
                    'inbox': float(probs[3])
                },
                'input_text': input_text
            }
            
            logger.debug(
                f"[{self.agent_name}] Model classified as {category} "
                f"(confidence: {confidence:.2f})"
            )
            
            # Log debug info
            self._log_debug_info(input_text, result)
            
            return result
        
        except Exception as e:
            logger.error(f"[{self.agent_name}] RKNN classification failed: {e}")
            logger.info(f"[{self.agent_name}] Falling back to rule-based classification")
            return self._classify_with_rules(email_data)

    def _classify_with_onnx(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify using ONNX model"""
        try:
            import numpy as np
            
            input_text = self._prepare_model_input(email_data)
            input_ids, attention_mask = self._tokenize_text(input_text)
            
            # ONNX inference
            inputs = {
                self.model.get_inputs()[0].name: input_ids.astype(np.int32),
                self.model.get_inputs()[1].name: attention_mask.astype(np.int32)
            }
            outputs = self.model.run(None, inputs)
            
            # Parse outputs
            logits = outputs[0][0]
            
            # Softmax
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / np.sum(exp_logits)
            
            predicted_class = int(np.argmax(probs))
            confidence = float(probs[predicted_class])
            
            class_names = ['transactions', 'feed', 'promotions', 'inbox']
            category = class_names[predicted_class]
            
            result = {
                'category': category,
                'confidence': confidence,
                'method': 'model (onnx)',
                'probabilities': {
                    'transactions': float(probs[0]),
                    'feed': float(probs[1]),
                    'promotions': float(probs[2]),
                    'inbox': float(probs[3])
                },
                'input_text': input_text
            }
            
            logger.debug(f"[{self.agent_name}] ONNX classified as {category} ({confidence:.2f})")
            self._log_debug_info(input_text, result)
            return result
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] ONNX classification failed: {e}")
            return self._classify_with_rules(email_data)
    
    def _prepare_model_input(self, email_data: Dict[str, Any]) -> str:
        """
        Prepare model input by concatenating fields with special separators
        
        Format: [SUBJECT] {subject} [SENDER] {sender} [BODY] {body}
        
        Args:
            email_data: Parsed email data
        
        Returns:
            Concatenated input string
        """
        subject = sanitize_text(email_data.get('subject', ''))
        sender_name = sanitize_text(email_data.get('from_name', ''))
        sender_email = sanitize_text(email_data.get('from_email', ''))
        sender = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        body = sanitize_text(email_data.get('body_text', '')[:1000])  # Limit body length
        
        # Concatenate with special separators
        input_text = f"[SUBJECT] {subject} [SENDER] {sender} [BODY] {body}"
        
        if not sender.strip():
            logger.warning(f"[{self.agent_name}] Empty sender in model input")
        if not body.strip():
            logger.warning(f"[{self.agent_name}] Empty body in model input")
        
        return input_text
    
    def _tokenize_text(self, text: str) -> tuple:
        """
        Tokenize text using HuggingFace tokenizer
        
        Args:
            text: Input text (already concatenated with special separators)
        
        Returns:
            Tuple of (input_ids, attention_mask) as numpy arrays
        """
        import numpy as np
        
        if not self.tokenizer:
            raise ClassificationError("Tokenizer not loaded")
        
        # Tokenize using HuggingFace tokenizer
        encoded = self.tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=self.max_length,
            return_tensors='np'
        )
        
        # Extract input_ids and attention_mask
        input_ids = encoded['input_ids'].astype(np.int64)
        attention_mask = encoded['attention_mask'].astype(np.int64)
        
        return input_ids, attention_mask
    
    def _classify_with_rules(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-based classification with 4 categories
        
        Categories:
        - Transactions: Money-related (bills, payments, stocks)
        - Feed: Newsletters, tutorials, announcements
        - Promotions: Sales, offers, unsolicited emails
        - Inbox: Everything else (default)
        
        Args:
            email_data: Parsed email data
        
        Returns:
            Classification result
        """
        subject = sanitize_text(email_data.get('subject', '')).lower()
        body = sanitize_text(email_data.get('body_text', '')).lower()
        from_email = sanitize_text(email_data.get('from_email', '')).lower()
        from_name = sanitize_text(email_data.get('from_name', '')).lower()
        
        # Combine text for analysis
        text = f"{subject} {body[:1000]}"  # Subject + first 1000 chars
        
        # Transaction indicators
        transaction_keywords = [
            'invoice', 'payment', 'bill', 'receipt', 'transaction',
            'charged', 'refund', 'stock', 'trade', 'dividend',
            'statement', 'balance', 'due', 'paid', 'purchase',
            'order', 'confirmation', 'shipped', 'delivery'
        ]
        
        transaction_domains = [
            'paypal', 'stripe', 'bank', 'zerodha', 'groww',
            'amazon', 'flipkart', 'razorpay'
        ]
        
        # Feed indicators
        feed_keywords = [
            'newsletter', 'digest', 'weekly', 'daily', 'tutorial',
            'launch', 'announcement', 'update', 'blog', 'article',
            'podcast', 'episode', 'issue', 'edition'
        ]
        
        feed_domains = [
            'substack', 'medium', 'beehiiv', 'buttondown',
            'mailchimp', 'convertkit'
        ]
        
        # Promotional indicators
        promo_keywords = [
            'sale', 'discount', 'offer', 'deal', 'limited time',
            'buy now', 'shop', 'coupon', 'free shipping',
            '%off', 'save', 'clearance', 'exclusive'
        ]
        
        promo_domains = [
            'marketing', 'promo', 'offers'
        ]
        
        # Count matches
        transaction_score = sum(1 for kw in transaction_keywords if kw in text)
        transaction_score += sum(2 for domain in transaction_domains if domain in from_email)
        
        feed_score = sum(1 for kw in feed_keywords if kw in text)
        feed_score += sum(2 for domain in feed_domains if domain in from_email)
        
        promo_score = sum(1 for kw in promo_keywords if kw in text)
        promo_score += sum(2 for domain in promo_domains if domain in from_email)
        
        # Check for unsubscribe link (strong feed/promo indicator)
        if 'unsubscribe' in text or 'opt-out' in text:
            # If has feed keywords, it's a newsletter
            if feed_score > 0:
                feed_score += 2
            else:
                promo_score += 3
        
        # Classify based on highest score
        scores = {
            'transactions': transaction_score,
            'feed': feed_score,
            'promotions': promo_score
        }
        
        max_score = max(scores.values())
        
        if max_score >= 2:
            # Get category with highest score
            category = max(scores, key=scores.get)
            confidence = min(0.5 + max_score * 0.1, 0.95)
        else:
            # Default to inbox
            category = 'inbox'
            confidence = 0.6
        
        result = {
                'category': category,
                'confidence': confidence,
                'method': 'rules',
                'scores': scores,
                'input_text': f"[SUBJECT] {subject} [SENDER] {from_name} <{from_email}> [BODY] {body[:1000]}"
            }
        
        logger.debug(
            f"[{self.agent_name}] Classified as {category} "
            f"(confidence: {confidence:.2f}, scores: {scores})"
        )
        
        # Log debug info (reconstruct input text for consistency)
        input_text = f"[SUBJECT] {subject} [SENDER] {from_name} <{from_email}> [BODY] {body[:1000]}"
        self._log_debug_info(input_text, result)
        
        return result
    
    def __del__(self):
        """Cleanup RKNN model on deletion"""
        if self.model:
            try:
                self.model.release()
            except Exception:
                pass


if __name__ == "__main__":
    # Test classifier
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Create classifier (no model)
    classifier = EmailClassifier(model_path=None, use_model=False, agent_name="test")
    
    # Test email 1: Promotional
    email1 = {
        'subject': '50% OFF Sale - Limited Time Only!',
        'body_text': 'Unsubscribe at the bottom. Amazing deals on everything...',
        'from_email': 'marketing@shop.com',
        'from_name': 'Shop Marketing'
    }
    
    print("\n[Test 1] Promotional email...")
    result1 = classifier.classify(email1)
    print(f"  Category: {result1['category']}")
    print(f"  Confidence: {result1['confidence']:.2f}")
    print(f"  Method: {result1['method']}")
    assert result1['category'] == 'promotions'
    
    # Test email 2: Transaction
    email2 = {
        'subject': 'Your Invoice from Amazon',
        'body_text': 'Thank you for your purchase. Your order has been charged...',
        'from_email': 'no-reply@amazon.com',
        'from_name': 'Amazon'
    }
    
    print("\n[Test 2] Transaction email...")
    result2 = classifier.classify(email2)
    print(f"  Category: {result2['category']}")
    print(f"  Confidence: {result2['confidence']:.2f}")
    assert result2['category'] == 'transactions'
    
    # Test email 3: Feed
    email3 = {
        'subject': 'Weekly Newsletter - Tech Updates',
        'body_text': 'Here are this week\'s top tech stories. Unsubscribe anytime.',
        'from_email': 'newsletter@techcrunch.com',
        'from_name': 'TechCrunch'
    }
    
    print("\n[Test 3] Feed email...")
    result3 = classifier.classify(email3)
    print(f"  Category: {result3['category']}")
    print(f"  Confidence: {result3['confidence']:.2f}")
    assert result3['category'] == 'feed'
    
    print("\n✓ All tests passed!")
