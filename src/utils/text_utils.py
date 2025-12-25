import re

def sanitize_text(text: str) -> str:
    """
    Sanitize text for CSV output by removing newlines, tabs, and other special characters.
    
    Args:
        text: Input text
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return str(text)
        
    # Replace newlines and tabs with spaces
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()
