"""
Module: repetition.py
Purpose: Person C - Repetition tracking for patient conversational patterns.

Monitors conversation history for repeated questions, concerns, or recurring topics
without using an external AI API or diagnosing medical conditions.
"""

from collections import Counter
import difflib
import re
from typing import Any, Dict, List, Optional, Set

# ==============================================================================
# CONFIGURATION CONSTANTS
# ==============================================================================

DEFAULT_HISTORY_WINDOW: int = 10
REPETITION_MEDIUM_THRESHOLD: int = 2
REPETITION_HIGH_THRESHOLD: int = 3
SIMILARITY_THRESHOLD: float = 0.65

# Standard English functional stopwords for content/topic isolation
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "will", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves"
}


def normalize_text(text: Optional[str]) -> str:
    """
    Normalize raw text deterministically.
    
    Steps:
    - Handle None or non-string input safely
    - Convert to lowercase
    - Strip punctuation and special characters
    - Collapse extra whitespace
    """
    if not text or not isinstance(text, str):
        return ""
    
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    normalized = " ".join(cleaned.split())
    return normalized


def extract_content_words(normalized_text: str) -> List[str]:
    """
    Extract meaningful non-stopword tokens from normalized text.
    """
    if not normalized_text:
        return []
    tokens = normalized_text.split()
    return [token for token in tokens if token not in STOP_WORDS and len(token) > 1]


class RepetitionTracker:
    """
    Tracks conversational repetition over a configurable sliding window.
    
    Maintains safe, isolated session state with zero global variables.
    """

    def __init__(
        self,
        history_window: int = DEFAULT_HISTORY_WINDOW,
        medium_threshold: int = REPETITION_MEDIUM_THRESHOLD,
        high_threshold: int = REPETITION_HIGH_THRESHOLD,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ) -> None:
        """
        Initialize the repetition tracker with configurable parameters.
        """
        self.history_window = max(1, history_window)
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.similarity_threshold = similarity_threshold
        self._history: List[str] = []

    def reset(self) -> None:
        """Clear conversation history for this tracker instance."""
        self._history.clear()

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute lightweight deterministic similarity between two normalized strings.
        """
        if not text_a or not text_b:
            return 0.0
        
        if text_a == text_b:
            return 1.0

        # Character sequence similarity
        seq_ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()

        tokens_a = set(text_a.split())
        tokens_b = set(text_b.split())

        if not tokens_a or not tokens_b:
            return seq_ratio

        # Token overlap ratio
        token_overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))

        # Content/topic word analysis
        cw_a = set(extract_content_words(text_a))
        cw_b = set(extract_content_words(text_b))

        if cw_a and cw_b:
            shared_content = cw_a & cw_b
            if shared_content:
                # If key topic/noun is shared (e.g. "daughter") and there is moderate structural similarity
                content_overlap = len(shared_content) / min(len(cw_a), len(cw_b))
                if content_overlap >= 0.8 and (seq_ratio >= 0.45 or token_overlap >= 0.35):
                    return max(seq_ratio, 0.75)

        return max(seq_ratio, token_overlap)

    def is_similar(self, text_a: str, text_b: str) -> bool:
        """Check if two normalized strings exceed the similarity threshold."""
        return self.calculate_similarity(text_a, text_b) >= self.similarity_threshold

    def analyze_message(
        self,
        message: Optional[str],
        external_history: Optional[List[str]] = None,
        update_internal_state: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze a patient message against conversation history for repetition.
        
        Args:
            message: The current patient message (may be None or empty).
            external_history: Optional external conversation history list.
                              If provided, uses this instead of internal history.
            update_internal_state: Whether to append the message to internal history.
            
        Returns:
            Dict containing repetition_count, repetition_level, repeated_topic, and is_repeating.
        """
        normalized_current = normalize_text(message)

        # Determine effective history to compare against
        if external_history is not None:
            raw_history = list(external_history)
        else:
            raw_history = list(self._history)

        # Normalize and filter window
        normalized_history = [
            normalize_text(item) for item in raw_history[-self.history_window:]
            if normalize_text(item)
        ]

        if not normalized_current:
            return {
                "repetition_count": 0,
                "repetition_level": "LOW",
                "repeated_topic": None,
                "is_repeating": False,
            }

        # Count occurrences in history that are identical or similar
        matching_messages = [
            past_msg for past_msg in normalized_history
            if self.is_similar(normalized_current, past_msg)
        ]

        # Total count includes past matching messages plus the current message itself
        repetition_count = len(matching_messages) + 1

        # Check intra-utterance repeated phrase/word (e.g. "my daughter my daughter my daughter...")
        current_content_words = extract_content_words(normalized_current)
        intra_count = 0
        intra_topic = None
        if current_content_words:
            word_counts = Counter(current_content_words)
            top_word, top_freq = word_counts.most_common(1)[0]
            if top_freq >= 3:
                intra_count = top_freq
                intra_topic = top_word

        if intra_count > repetition_count:
            repetition_count = intra_count

        # Classify repetition level
        if repetition_count >= self.high_threshold:
            repetition_level = "HIGH"
            is_repeating = True
        elif repetition_count >= self.medium_threshold:
            repetition_level = "MEDIUM"
            is_repeating = True
        else:
            repetition_level = "LOW"
            is_repeating = False

        # Extract repeated topic if repetition is detected
        repeated_topic: Optional[str] = intra_topic
        if not repeated_topic and repetition_count >= self.medium_threshold:
            all_matching = matching_messages + [normalized_current]
            content_tokens: List[str] = []
            for msg in all_matching:
                content_tokens.extend(extract_content_words(msg))
            
            if content_tokens:
                counts = Counter(content_tokens)
                most_common, freq = counts.most_common(1)[0]
                if freq >= 2:
                    repeated_topic = most_common

        # Update internal state if requested and no external history was used
        if update_internal_state and external_history is None:
            self._history.append(normalized_current)
            if len(self._history) > self.history_window * 2:
                self._history = self._history[-self.history_window:]

        return {
            "repetition_count": repetition_count,
            "repetition_level": repetition_level,
            "repeated_topic": repeated_topic,
            "is_repeating": is_repeating,
        }
