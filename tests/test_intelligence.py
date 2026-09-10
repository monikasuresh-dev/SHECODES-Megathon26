"""
Test Suite: test_intelligence.py
Purpose: Person C - Verification and validation for Intelligence Layer.

Covers all repetition, distress, and risk classification unit tests.
"""

import json
import os
import sys
import unittest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.repetition import (
    RepetitionTracker,
    normalize_text,
    DEFAULT_HISTORY_WINDOW,
    REPETITION_MEDIUM_THRESHOLD,
    REPETITION_HIGH_THRESHOLD,
    SIMILARITY_THRESHOLD,
)
from backend.distress import (
    DistressScorer,
    DISTRESS_LOW_THRESHOLD,
    DISTRESS_MODERATE_THRESHOLD,
    DISTRESS_HIGH_THRESHOLD,
)
from backend.intelligence import IntelligenceEngine


class TestRepetitionTracker(unittest.TestCase):
    """Tests for RepetitionTracker."""

    def setUp(self) -> None:
        self.tracker = RepetitionTracker(history_window=10)

    def test_text_normalization(self) -> None:
        """Verify normalization removes punctuation, lowers case, and collapses whitespace."""
        raw = "   Where... IS   my DAUGHTER???   "
        self.assertEqual(normalize_text(raw), "where is my daughter")
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text("   "), "")

    def test_exact_repetition(self) -> None:
        """Verify exact repeated questions are detected."""
        res1 = self.tracker.analyze_message("Where is my daughter?")
        self.assertEqual(res1["repetition_count"], 1)
        self.assertEqual(res1["repetition_level"], "LOW")
        self.assertFalse(res1["is_repeating"])

        res2 = self.tracker.analyze_message("Where is my daughter?")
        self.assertEqual(res2["repetition_count"], 2)
        self.assertEqual(res2["repetition_level"], "MEDIUM")
        self.assertTrue(res2["is_repeating"])

        res3 = self.tracker.analyze_message("Where is my daughter?")
        self.assertEqual(res3["repetition_count"], 3)
        self.assertEqual(res3["repetition_level"], "HIGH")
        self.assertTrue(res3["is_repeating"])
        self.assertEqual(res3["repeated_topic"], "daughter")

    def test_similar_phrasing_detection(self) -> None:
        """Verify semantic variations of the same concern are detected."""
        self.tracker.analyze_message("Where is my daughter?")
        res2 = self.tracker.analyze_message("Is my daughter here?")
        res3 = self.tracker.analyze_message("When will my daughter come?")
        
        self.assertTrue(res3["is_repeating"])
        self.assertEqual(res3["repetition_level"], "HIGH")
        self.assertEqual(res3["repeated_topic"], "daughter")

    def test_history_window_sliding(self) -> None:
        """Verify messages roll off when history window is exceeded."""
        short_tracker = RepetitionTracker(history_window=3)
        short_tracker.analyze_message("Where is my daughter?")
        short_tracker.analyze_message("I like tea.")
        short_tracker.analyze_message("Nice weather.")
        short_tracker.analyze_message("The cat is asleep.")
        res = short_tracker.analyze_message("Where is my daughter?")
        self.assertEqual(res["repetition_count"], 1)
        self.assertEqual(res["repetition_level"], "LOW")


class TestDistressScorer(unittest.TestCase):
    """Tests for DistressScorer."""

    def setUp(self) -> None:
        self.scorer = DistressScorer()

    def test_calm_message(self) -> None:
        """Verify normal statements receive 0 or low distress score."""
        res = self.scorer.score_single_text("Good morning. What is the weather today?")
        self.assertEqual(res["distress_score"], 0)
        self.assertEqual(res["distress_level"], "LOW")
        self.assertEqual(len(res["signals"]), 0)

    def test_mild_worry_not_overweighted(self) -> None:
        """Verify routine emotional statement does not trigger high panic."""
        res = self.scorer.score_single_text("I am a little worried about tomorrow.")
        self.assertLessEqual(res["distress_score"], DISTRESS_LOW_THRESHOLD)
        self.assertEqual(res["distress_level"], "LOW")

    def test_moderate_distress(self) -> None:
        """Verify moderate confusion produces MODERATE level."""
        res = self.scorer.score_single_text("I am confused and worried.")
        self.assertGreater(res["distress_score"], DISTRESS_LOW_THRESHOLD)
        self.assertLessEqual(res["distress_score"], DISTRESS_MODERATE_THRESHOLD)
        self.assertEqual(res["distress_level"], "MODERATE")

    def test_high_distress_compound(self) -> None:
        """Verify multiple compounding distress indicators produce HIGH score."""
        res = self.scorer.score_single_text("I'm scared. I don't know where I am. Please help me.")
        self.assertGreaterEqual(res["distress_score"], DISTRESS_HIGH_THRESHOLD)
        self.assertEqual(res["distress_level"], "HIGH")
        types = [s["type"] for s in res["signals"]]
        self.assertIn("fear", types)
        self.assertIn("confusion", types)
        self.assertIn("help_request", types)


class TestIntelligenceEngineScenarios(unittest.TestCase):
    """Full tests for IntelligenceEngine."""

    def setUp(self) -> None:
        self.engine = IntelligenceEngine()

    def test_1_normal_conversation(self) -> None:
        result = self.engine.process_message("Good morning. What is the weather today?")
        self.assertEqual(result["risk_level"], "GREEN")
        self.assertFalse(result["escalate"])
        self.assertIn("Normal conversation", result["reason"])

    def test_2_single_question(self) -> None:
        result = self.engine.process_message("Where is my daughter?")
        self.assertNotEqual(result["risk_level"], "RED")
        self.assertFalse(result["escalate"])

    def test_3_repeated_question(self) -> None:
        self.engine.process_message("Where is my daughter?")
        self.engine.process_message("Where is my daughter?")
        result = self.engine.process_message("Where is my daughter?")
        
        self.assertEqual(result["repetition_level"], "HIGH")
        self.assertGreaterEqual(result["repetition_count"], 3)
        self.assertEqual(result["risk_level"], "YELLOW")
        self.assertFalse(result["escalate"])

    def test_4_moderate_distress(self) -> None:
        result = self.engine.process_message("I am confused and worried.")
        self.assertEqual(result["distress_level"], "MODERATE")
        self.assertNotEqual(result["risk_level"], "RED")
        self.assertEqual(result["risk_level"], "YELLOW")
        self.assertFalse(result["escalate"])

    def test_5_high_distress(self) -> None:
        result = self.engine.process_message("I'm scared. I don't know where I am. Please help me.")
        self.assertEqual(result["distress_level"], "HIGH")
        self.assertEqual(result["risk_level"], "RED")
        self.assertTrue(result["escalate"])

    def test_6_repeated_and_distressed(self) -> None:
        self.engine.process_message("I don't know where my daughter is.")
        self.engine.process_message("I don't know where my daughter is.")
        self.engine.process_message("I'm scared.")
        result = self.engine.process_message("Please help me.")

        self.assertEqual(result["distress_level"], "HIGH")
        self.assertEqual(result["risk_level"], "RED")
        self.assertTrue(result["escalate"])

    def test_7_different_wording(self) -> None:
        self.engine.process_message("Where is my daughter?")
        self.engine.process_message("Is my daughter here?")
        result = self.engine.process_message("When will my daughter come?")
        
        self.assertEqual(result["repetition_level"], "HIGH")
        self.assertTrue(result["repetition_count"] >= 3)
        self.assertEqual(result["risk_level"], "YELLOW")

    def test_8_normal_after_repetition(self) -> None:
        self.engine.process_message("Where is my daughter?")
        self.engine.process_message("Where is my daughter?")
        self.engine.process_message("Where is my daughter?")
        
        normal_result = self.engine.process_message("The soup was delicious today. Thank you.")
        self.assertNotEqual(normal_result["risk_level"], "RED")
        self.assertEqual(normal_result["risk_level"], "GREEN")
        self.assertFalse(normal_result["escalate"])

    def test_9_empty_input(self) -> None:
        result = self.engine.process_message("")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["risk_level"], "GREEN")
        self.assertFalse(result["escalate"])

    def test_10_none_input(self) -> None:
        result = self.engine.process_message(None)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["risk_level"], "GREEN")
        self.assertFalse(result["escalate"])

    def test_11_json_serializability(self) -> None:
        result = self.engine.process_message("I'm scared. Please help me.")
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["risk_level"], "RED")
        self.assertEqual(deserialized["escalate"], True)

    def test_12_explainability_contract(self) -> None:
        result = self.engine.process_message("Where is my daughter?")
        self.assertIn("reason", result)
        self.assertTrue(len(result["reason"]) > 0)
        self.assertIn("signals", result)
        self.assertIsInstance(result["signals"], list)

    def test_13_multi_session_isolation(self) -> None:
        engine_a = IntelligenceEngine(conversation_id="patient_alice")
        engine_b = IntelligenceEngine(conversation_id="patient_bob")

        engine_a.process_message("Where is my purse?")
        engine_a.process_message("Where is my purse?")
        res_a = engine_a.process_message("Where is my purse?")
        self.assertEqual(res_a["repetition_level"], "HIGH")

        res_b = engine_b.process_message("Good morning.")
        self.assertEqual(res_b["repetition_level"], "LOW")
        self.assertEqual(res_b["risk_level"], "GREEN")


if __name__ == "__main__":
    unittest.main()
