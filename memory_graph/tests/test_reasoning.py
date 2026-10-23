"""The reasoning layer's model call (T6.7b, memory_graph/reasoning.py).

A stand-in model is used here, so the tests need no GPU and no weights. The
same call with the real Qwen model is in test_reasoning_model.py.

Proposed done-when: a good reply gives the right lists, and every kind of bad
reply, a model error and a model that runs past the time limit fall back to
the CLIP list within the limit. The parser tests need only the standard
library. The ones that use ClassExpander need numpy, and skip without it.
"""

import threading
import time
import unittest

from memory_graph.config import MemoryGraphConfig
from memory_graph.reasoning import build_messages, parse_reply
from memory_graph.vocabulary import Vocabulary

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on the machine
    np = None

BASE = ("chair", "table", "desk", "sofa", "plant", "cup")
BG = ("wall", "floor")


def vocab():
    return Vocabulary(BASE, BG)


class PromptTest(unittest.TestCase):
    def test_the_prompt_lists_the_vocabulary_in_id_order_and_the_instruction(self):
        system, user = build_messages("  find   a chair ", vocab())
        self.assertEqual(system["role"], "system")
        self.assertEqual(user["role"], "user")
        self.assertIn("chair, table, desk, sofa, plant, cup", user["content"])
        self.assertIn('Instruction: "find a chair"', user["content"])

    def test_the_example_in_the_prompt_is_valid_json(self):
        _, user = build_messages("find a chair", vocab())
        parsed, why = parse_reply(user["content"].split("Example.")[1], vocab())
        self.assertEqual(why, "")
        self.assertEqual(parsed.targets, ("pen",))

    def test_the_synonym_example_maps_to_the_list_and_related_is_asked_for(self):
        """T6.7: 1.5B kept "couch" as a new class and left related empty."""
        _, user = build_messages("find a chair", vocab())
        parsed, _ = parse_reply(user["content"].split("Example, with sofa in the list.")[1], vocab())
        self.assertEqual(parsed.targets, ("sofa",))
        self.assertIn("2 to 5 objects", user["content"])
        self.assertNotIn("Leave it empty", user["content"])


class ParseReplyTest(unittest.TestCase):
    def parse(self, reply, **kwargs):
        return parse_reply(reply, vocab(), **kwargs)

    def test_a_good_reply(self):
        parsed, why = self.parse('{"targets": ["chair"], "related": ["table", "desk"]}')
        self.assertEqual(why, "")
        self.assertEqual(parsed.targets, ("chair",))
        self.assertEqual(parsed.related, ("table", "desk"))

    def test_json_inside_prose_and_code_fences(self):
        reply = 'Sure! Here you go:\n```json\n{"targets": ["Chair"], "related": ["Table"]}\n```\nHope it helps.'
        parsed, _ = self.parse(reply)
        self.assertEqual((parsed.targets, parsed.related), (("chair",), ("table",)))

    def test_a_brace_before_the_object_is_skipped(self):
        parsed, _ = self.parse('{not json} then {"targets": ["cup"]}')
        self.assertEqual(parsed.targets, ("cup",))

    def test_comma_separated_strings_and_upstream_key_names(self):
        parsed, _ = self.parse('{"target": "chair", "relevant": "table, desk"}')
        self.assertEqual((parsed.targets, parsed.related), (("chair",), ("table", "desk")))

    def test_a_new_target_is_kept_a_new_related_class_is_not(self):
        """Upstream: related classes must be in the list (vlm.py:96), a target may be new."""
        parsed, _ = self.parse('{"targets": ["Water Bottle"], "related": ["fridge", "table"]}')
        self.assertEqual(parsed.targets, ("water bottle",))
        self.assertEqual(parsed.related, ("table",))

    def test_a_target_is_not_also_related(self):
        parsed, _ = self.parse('{"targets": ["chair"], "related": ["chair", "table"]}')
        self.assertEqual(parsed.related, ("table",))

    def test_a_synonym_becomes_the_list_class(self):
        """T6.7: "couch" with sofa in the list. Related names are mapped too, and a
        synonym that lands on a class already named is a repeat."""
        synonyms = [("couch", "sofa"), ("bin", "trash can")]
        parsed, _ = self.parse('{"targets": ["Couch", "sofa"], "related": ["couch", "table"]}',
                               synonyms=synonyms)
        self.assertEqual((parsed.targets, parsed.related), (("sofa",), ("table",)))
        parsed, _ = self.parse('{"targets": ["bin"]}', synonyms=synonyms)
        self.assertEqual(parsed.targets, ("trash can",))   # not in this list, so a new class

    def test_without_synonyms_a_synonym_is_a_new_class(self):
        parsed, _ = self.parse('{"targets": ["couch"]}')
        self.assertEqual(parsed.targets, ("couch",))

    def test_underscore_and_space_match_the_lists_spelling(self):
        """T6.7: both models wrote fire_extinguisher. The list keeps its own spelling."""
        v = Vocabulary(BASE + ("tv_monitor",), BG)
        parsed, _ = parse_reply('{"targets": ["TV monitor", "Fire_Extinguisher"], '
                                '"related": ["tv monitor", "trash_can"]}', v)
        self.assertEqual(parsed.targets, ("tv_monitor", "fire extinguisher"))
        self.assertEqual(parsed.related, ())   # tv_monitor is a target, trash can not in the list

    def test_repeats_background_and_rambling_names_are_dropped(self):
        reply = ('{"targets": ["wall", "a chair that is next to the big table", "chair!", "chair", "Chair"],'
                 ' "related": ["floor", "table", "table"]}')
        parsed, _ = self.parse(reply)
        self.assertEqual((parsed.targets, parsed.related), (("chair",), ("table",)))

    def test_lists_are_cut_to_the_maximum_in_the_models_order(self):
        reply = '{"targets": ["cup", "chair", "sofa", "plant"], "related": ["table", "desk"]}'
        parsed, _ = self.parse(reply, max_targets=2, max_related=1)
        self.assertEqual((parsed.targets, parsed.related), (("cup", "chair"), ("table",)))

    def test_no_related_is_fine(self):
        parsed, why = self.parse('{"targets": ["chair"]}')
        self.assertEqual((why, parsed.related), ("", ()))

    def test_unusable_replies(self):
        for reply, why in [
            (None, "empty reply"),
            ("   ", "empty reply"),
            ("chair\nbecause\ntable\nbecause", "no JSON object in the reply"),
            ('{"targets": ', "no JSON object in the reply"),
            ('["chair"]', "no JSON object in the reply"),
            ('{"targets": [], "related": ["table"]}', "no usable target in the reply"),
            ('{"targets": ["wall"]}', "no usable target in the reply"),
            ('{"targets": [3, null]}', "no usable target in the reply"),
            ('{"answer": "chair"}', "no usable target in the reply"),
        ]:
            with self.subTest(reply=reply):
                self.assertEqual(self.parse(reply), (None, why))


class FakeModel:
    """Stand-in chat model: returns a fixed reply, raises, or blocks until
    released. Records the messages and limits it was called with."""

    def __init__(self, reply="", error=None, block=False):
        self.text, self.error = reply, error
        self.release = threading.Event()
        if not block:
            self.release.set()
        self.calls = []

    def reply(self, messages, max_new_tokens, max_time):
        self.calls.append((messages, max_new_tokens, max_time))
        self.release.wait(5.0)
        if self.error:
            raise self.error
        return self.text


@unittest.skipIf(np is None, "needs numpy")
class ClassExpanderTest(unittest.TestCase):
    def setUp(self):
        from memory_graph.tests.test_task import WordEncoder  # needs numpy
        self.encoder = WordEncoder()
        self.cfg = MemoryGraphConfig(reasoning_timeout_s=0.3)
        self.models = []

    def tearDown(self):
        for model in self.models:
            if model is not None:
                model.release.set()

    def expand(self, model, instruction="find a chair", v=None):
        from memory_graph.reasoning import ClassExpander
        from memory_graph.task import TaskContext
        self.models.append(model)
        self.vocab = vocab() if v is None else v
        task = TaskContext.from_text(instruction, self.encoder)
        return ClassExpander(model, self.encoder, self.cfg).expand(task, self.vocab)

    def test_a_good_reply_fills_the_task(self):
        model = FakeModel('{"targets": ["chair"], "related": ["table", "desk"]}')
        result = self.expand(model)
        self.assertEqual((result.source, result.why), ("model", ""))
        self.assertEqual(result.task.targets, {"chair"})
        self.assertEqual(result.task.related, {"table", "desk"})
        self.assertEqual(result.added, ())
        self.assertEqual(len(self.vocab), len(BASE))

    def test_ranked_keeps_the_models_order_in_the_vocabulary_spelling(self):
        """The task holds its targets as a set, so the order lives in `ranked`."""
        result = self.expand(FakeModel('{"targets": ["Sofa", "chair"]}'))
        self.assertEqual(result.ranked, ("sofa", "chair"))

    def test_the_model_gets_the_prompt_and_the_limits(self):
        model = FakeModel('{"targets": ["chair"]}')
        self.expand(model)
        messages, max_new_tokens, max_time = model.calls[0]
        self.assertEqual(messages, build_messages("find a chair", vocab()))
        self.assertEqual((max_new_tokens, max_time), (self.cfg.reasoning_max_new_tokens, 0.3))

    def test_a_new_target_is_appended_to_the_vocabulary(self):
        """The round trip with T6.7c: the new class gets the next id."""
        result = self.expand(FakeModel('{"targets": ["Water Bottle"], "related": ["table"]}'))
        self.assertEqual(result.added, ("water bottle",))
        self.assertEqual(self.vocab.id_of("water bottle"), len(BASE))
        self.assertEqual(result.task.targets, {"water bottle"})

    def test_an_unusable_reply_falls_back_to_clip(self):
        """Upstream's rule: the stand-in encoder puts "find a chair" on the chair
        axis, so chair is the only class within 95 % of the best."""
        result = self.expand(FakeModel("I think you should look for a chair."))
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.why, "no JSON object in the reply")
        self.assertEqual(result.reply, "I think you should look for a chair.")
        self.assertEqual((result.task.targets, result.task.related), ({"chair"}, frozenset()))
        self.assertEqual(result.added, ())
        self.assertEqual(result.ranked, ("chair",))

    def test_a_model_error_falls_back(self):
        result = self.expand(FakeModel(error=RuntimeError("CUDA out of memory")))
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.why, "the model failed: RuntimeError: CUDA out of memory")
        self.assertIsNone(result.reply)
        self.assertEqual(result.task.targets, {"chair"})

    def test_no_model_falls_back(self):
        result = self.expand(None)
        self.assertEqual((result.source, result.why), ("fallback", "no model"))
        self.assertEqual(result.task.targets, {"chair"})

    def test_a_stuck_model_falls_back_within_the_time_limit(self):
        start = time.monotonic()
        result = self.expand(FakeModel('{"targets": ["sofa"]}', block=True))
        elapsed = time.monotonic() - start
        self.assertEqual((result.source, result.why), ("fallback", "no reply within 0.3 s"))
        self.assertEqual(result.task.targets, {"chair"})
        self.assertLess(elapsed, 1.0)
        self.assertGreaterEqual(result.seconds, 0.3)

    def test_while_a_stuck_call_runs_the_next_task_goes_straight_to_the_fall_back(self):
        from memory_graph.reasoning import ClassExpander
        from memory_graph.task import TaskContext
        model = FakeModel('{"targets": ["sofa"]}', block=True)
        self.models.append(model)
        expander = ClassExpander(model, self.encoder, self.cfg)
        expander.expand(TaskContext.from_text("find a chair", self.encoder), vocab())
        second = expander.expand(TaskContext.from_text("find a sofa", self.encoder), vocab())
        self.assertEqual(second.why, "the previous model call is still running")
        self.assertEqual(second.task.targets, {"sofa"})
        self.assertEqual(len(model.calls), 1)
        model.release.set()
        expander._running.join(1.0)
        third = expander.expand(TaskContext.from_text("find a sofa", self.encoder), vocab())
        self.assertEqual(third.source, "model")

    def test_the_old_classes_of_the_task_are_replaced(self):
        from memory_graph.reasoning import ClassExpander
        from memory_graph.task import TaskContext
        task = TaskContext.from_text("find a chair", self.encoder, targets={"plant"}, related={"cup"})
        result = ClassExpander(FakeModel('{"targets": ["chair"]}'), self.encoder, self.cfg).expand(task, vocab())
        self.assertEqual((result.task.targets, result.task.related), ({"chair"}, frozenset()))

    def test_the_config_synonyms_are_used(self):
        result = self.expand(FakeModel('{"targets": ["couch"], "related": ["chair"]}'))
        self.assertEqual((result.task.targets, result.task.related), ({"sofa"}, {"chair"}))
        self.assertEqual(result.added, ())

    def test_the_fall_back_makes_only_the_best_class_a_target(self):
        """T6.7: the rest of upstream's list becomes related. The stand-in encoder
        puts "chair sofa" equally near chair and sofa, and the tie keeps list order."""
        result = self.expand(None, instruction="chair sofa")
        self.assertEqual(result.source, "fallback")
        self.assertEqual((result.task.targets, result.task.related), ({"chair"}, {"sofa"}))
        self.assertEqual(result.ranked, ("chair",))

    def test_the_fall_backs_related_are_cut_to_the_maximum(self):
        from memory_graph.reasoning import ClassExpander
        from memory_graph.task import TaskContext
        cfg = MemoryGraphConfig(reasoning_max_related=0)
        task = TaskContext.from_text("chair sofa", self.encoder)
        result = ClassExpander(None, self.encoder, cfg).expand(task, vocab())
        self.assertEqual((result.task.targets, result.task.related), ({"chair"}, frozenset()))


@unittest.skipIf(np is None, "needs numpy")
class FallbackTargetsTest(unittest.TestCase):
    def setUp(self):
        from memory_graph.tests.test_task import WordEncoder
        from memory_graph.task import TaskContext
        self.encoder = WordEncoder()
        self.task = lambda text: TaskContext.from_text(text, self.encoder)

    def fallback(self, text, phrases, **kwargs):
        from memory_graph.reasoning import fallback_targets
        return fallback_targets(self.task(text), phrases, self.encoder, **kwargs)

    def test_only_classes_near_the_best_are_kept(self):
        self.assertEqual(self.fallback("find a chair", BASE), ["chair"])

    def test_best_first_ties_in_vocabulary_order_cut_to_top_k(self):
        """"chair or sofa" is halfway between the two axes: "chair sofa" scores
        1, chair and sofa tie at 0.71, plant scores 0."""
        phrases = ["sofa", "plant", "chair", "chair sofa"]
        self.assertEqual(self.fallback("chair or sofa", phrases), ["chair sofa"])
        self.assertEqual(self.fallback("chair or sofa", phrases, ratio=0.7), ["chair sofa", "sofa", "chair"])
        self.assertEqual(self.fallback("chair or sofa", phrases, ratio=0.7, top_k=2), ["chair sofa", "sofa"])

    def test_a_negative_best_still_keeps_the_best(self):
        class Flipped:
            def encode_text(self, texts):
                return np.array([[1.0, 0.0]] if texts == ["task"] else [[-1.0, 0.1], [-1.0, 0.5]])
        from memory_graph.reasoning import fallback_targets
        from memory_graph.task import TaskContext
        task = TaskContext.from_text("task", Flipped())
        # cos is -0.995 for a and -0.894 for b. Upstream's 0.95 * best would keep neither.
        self.assertEqual(fallback_targets(task, ["a", "b"], Flipped()), ["b"])

    def test_an_empty_vocabulary(self):
        self.assertEqual(self.fallback("find a chair", []), [])


class ConfigTest(unittest.TestCase):
    def test_bad_reasoning_settings_are_refused(self):
        for bad in [{"reasoning_timeout_s": 0}, {"reasoning_max_targets": 0},
                    {"reasoning_max_related": -1}, {"fallback_ratio": 0.0},
                    {"fallback_ratio": 1.5}, {"fallback_top_k": 0}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MemoryGraphConfig.from_dict(bad)

    def test_bad_synonyms_are_refused(self):
        for bad in [[("chair", "sofa")],                       # renames a class in the list
                    [("couch", "sofa"), ("Couch", "chair")],   # the same name twice
                    [("", "sofa")]]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MemoryGraphConfig.from_dict({"class_synonyms": bad})

    def test_synonyms_load_from_a_mapping_or_pairs(self):
        a = MemoryGraphConfig.from_dict({"class_synonyms": {"couch": "sofa", "tv": "tv monitor"}})
        b = MemoryGraphConfig.from_dict({"class_synonyms": [["couch", "sofa"], ["tv", "tv monitor"]]})
        self.assertEqual(a.class_synonyms, (("couch", "sofa"), ("tv", "tv monitor")))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
