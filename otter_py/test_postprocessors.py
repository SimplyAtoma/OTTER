"""
Unit tests for the new post-processors:
  - filter_fillers
  - filter_low_confidence
"""
import unittest

# Import triggers @register_postprocessor decorators
from otter_py.pipelines.postprocessors.filter_fillers import filter_fillers, DEFAULT_FILLERS
from otter_py.pipelines.postprocessors.filter_low_confidence_words import filter_low_confidence


def w(word, start=0.0, end=0.5, conf=None):
    """Helper: build a Word dict."""
    d = {"word": word, "start": start, "end": end}
    if conf is not None:
        d["conf"] = conf
    return d


class TestFilterFillers(unittest.TestCase):

    # ------------------------------------------------------------------
    # Basic removal
    # ------------------------------------------------------------------

    def test_removes_default_fillers(self):
        words = [w("Hello"), w("uh"), w("world"), w("um")]
        out, meta = filter_fillers(words, {}, {})
        self.assertEqual([x["word"] for x in out], ["Hello", "world"])
        self.assertEqual(meta["removed"], 2)

    def test_removes_filler_with_punctuation(self):
        """Trailing punctuation on the word should still match."""
        words = [w("uh,"), w("hello")]
        out, meta = filter_fillers(words, {}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 1)

    def test_case_insensitive(self):
        words = [w("UH"), w("Um"), w("hello")]
        out, meta = filter_fillers(words, {}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 2)

    def test_non_filler_words_kept(self):
        words = [w("hello"), w("world")]
        out, meta = filter_fillers(words, {}, {})
        self.assertEqual(len(out), 2)
        self.assertEqual(meta["removed"], 0)

    def test_empty_input(self):
        out, meta = filter_fillers([], {}, {})
        self.assertEqual(out, [])
        self.assertEqual(meta["removed"], 0)

    # ------------------------------------------------------------------
    # Custom fillers list
    # ------------------------------------------------------------------

    def test_custom_fillers(self):
        words = [w("like"), w("basically"), w("hello")]
        out, meta = filter_fillers(words, {"fillers": ["like", "basically"]}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 2)

    def test_default_fillers_not_removed_when_custom_list_set(self):
        """Setting a custom list replaces the defaults."""
        words = [w("uh"), w("like"), w("hello")]
        out, _ = filter_fillers(words, {"fillers": ["like"]}, {})
        # "uh" should survive because it's not in the custom list
        words_out = [x["word"] for x in out]
        self.assertIn("uh", words_out)
        self.assertNotIn("like", words_out)

    # ------------------------------------------------------------------
    # min_conf gating
    # ------------------------------------------------------------------

    def test_min_conf_removes_low_confidence_filler(self):
        """Filler with conf < min_conf should be removed."""
        words = [w("uh", conf=0.2), w("hello")]
        out, meta = filter_fillers(words, {"min_conf": 0.5}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 1)

    def test_min_conf_keeps_high_confidence_filler(self):
        """Filler with conf >= min_conf should be kept."""
        words = [w("uh", conf=0.9), w("hello")]
        out, meta = filter_fillers(words, {"min_conf": 0.5}, {})
        self.assertEqual([x["word"] for x in out], ["uh", "hello"])
        self.assertEqual(meta["removed"], 0)

    def test_min_conf_filler_without_conf_score_is_removed(self):
        """Filler with no conf score and min_conf set should still be removed."""
        words = [w("uh"), w("hello")]  # no conf key
        out, meta = filter_fillers(words, {"min_conf": 0.5}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 1)

    def test_no_min_conf_removes_all_fillers_regardless_of_confidence(self):
        words = [w("uh", conf=0.99), w("hello")]
        out, meta = filter_fillers(words, {}, {})
        self.assertEqual([x["word"] for x in out], ["hello"])
        self.assertEqual(meta["removed"], 1)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def test_meta_filler_set_contains_defaults(self):
        _, meta = filter_fillers([w("hello")], {}, {})
        for filler in DEFAULT_FILLERS:
            self.assertIn(filler, meta["filler_set"])


class TestFilterLowConfidence(unittest.TestCase):

    # ------------------------------------------------------------------
    # Basic removal
    # ------------------------------------------------------------------

    def test_removes_low_confidence_words(self):
        words = [w("hello", conf=0.9), w("uh", conf=0.1), w("world", conf=0.8)]
        out, meta = filter_low_confidence(words, {"min_conf": 0.4}, {})
        self.assertEqual([x["word"] for x in out], ["hello", "world"])
        self.assertEqual(meta["removed"], 1)
        self.assertEqual(meta["replaced"], 0)

    def test_keeps_words_at_threshold(self):
        """Words exactly at min_conf should be kept (not strictly less than)."""
        words = [w("hello", conf=0.4)]
        out, meta = filter_low_confidence(words, {"min_conf": 0.4}, {})
        self.assertEqual(len(out), 1)
        self.assertEqual(meta["removed"], 0)

    def test_removes_all_below_threshold(self):
        words = [w("a", conf=0.1), w("b", conf=0.2), w("c", conf=0.3)]
        out, meta = filter_low_confidence(words, {"min_conf": 0.5}, {})
        self.assertEqual(out, [])
        self.assertEqual(meta["removed"], 3)

    def test_empty_input(self):
        out, meta = filter_low_confidence([], {}, {})
        self.assertEqual(out, [])
        self.assertEqual(meta["removed"], 0)
        self.assertEqual(meta["replaced"], 0)

    # ------------------------------------------------------------------
    # Replace mode
    # ------------------------------------------------------------------

    def test_replace_with_placeholder(self):
        words = [w("hello", conf=0.9), w("mumble", conf=0.1), w("world", conf=0.8)]
        out, meta = filter_low_confidence(words, {"min_conf": 0.4, "replace_with": "[?]"}, {})
        self.assertEqual([x["word"] for x in out], ["hello", "[?]", "world"])
        self.assertEqual(meta["replaced"], 1)
        self.assertEqual(meta["removed"], 0)

    def test_replace_preserves_timestamps(self):
        words = [w("mumble", start=1.0, end=1.5, conf=0.1)]
        out, _ = filter_low_confidence(words, {"min_conf": 0.4, "replace_with": "[?]"}, {})
        self.assertEqual(out[0]["start"], 1.0)
        self.assertEqual(out[0]["end"], 1.5)

    # ------------------------------------------------------------------
    # Unscored words
    # ------------------------------------------------------------------

    def test_keep_unscored_true_by_default(self):
        """Words without a confidence score should be kept by default."""
        words = [w("hello"), w("world")]  # no conf key
        out, meta = filter_low_confidence(words, {"min_conf": 0.4}, {})
        self.assertEqual(len(out), 2)
        self.assertEqual(meta["removed"], 0)

    def test_keep_unscored_false_removes_unscored(self):
        words = [w("hello"), w("scored", conf=0.9)]
        out, meta = filter_low_confidence(words, {"min_conf": 0.4, "keep_unscored": False}, {})
        self.assertEqual([x["word"] for x in out], ["scored"])
        self.assertEqual(meta["removed"], 1)

    # ------------------------------------------------------------------
    # Default threshold
    # ------------------------------------------------------------------

    def test_default_threshold_is_0_4(self):
        words = [w("kept", conf=0.5), w("dropped", conf=0.3)]
        out, meta = filter_low_confidence(words, {}, {})
        self.assertEqual([x["word"] for x in out], ["kept"])
        self.assertEqual(meta["min_conf"], 0.4)


if __name__ == "__main__":
    unittest.main()
