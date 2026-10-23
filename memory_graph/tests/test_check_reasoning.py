"""T6.7's check script (memory_graph/check_reasoning.py), with a stand-in model
and the stand-in word encoder, so no GPU and no weights. The real run is on the
lab box, its record in docs/bench-runs/.
"""

import json
import tempfile
import unittest
from pathlib import Path

import memory_graph.tests._requires_numpy  # noqa: F401  (skips this module without numpy)
from memory_graph.check_reasoning import DEFAULT_SET, FALLBACK, Item, check, load_set, markdown, round_trip, run_set
from memory_graph.config import MemoryGraphConfig
from memory_graph.reasoning import ClassExpander

import numpy as np

BASE = ("chair", "sofa", "plant", "cup", "desk")


class WordEncoder:
    """Stand-in text encoder: one axis per base class, and one more shared by
    every other word, so no sentence is a zero vector."""

    def encode_text(self, texts):
        out = np.zeros((len(texts), len(BASE) + 1))
        for row, text in enumerate(texts):
            for word in text.split():
                out[row, BASE.index(word) if word in BASE else len(BASE)] += 1.0
        return out


class ScriptedModel:
    """Stand-in chat model: a fixed reply per instruction, the prompt's last one
    (the prompt's examples have instructions too)."""

    def __init__(self, replies):
        self.replies = replies

    def reply(self, messages, max_new_tokens, max_time):
        instruction = messages[-1]["content"].rsplit('Instruction: "', 1)[1].split('"')[0]
        return self.replies[instruction]


ITEMS = (
    Item("find a chair", "in the list", ("chair",)),
    Item("find the couch", "synonym", ("sofa",)),
    Item("find a mug on the desk", "relation", ("cup",), ("desk",)),
    Item("find a lamp", "not in the list", ("lamp",)),
)
REPLIES = {
    "find a chair": '{"targets": ["chair"], "related": ["desk"]}',
    "find the couch": '{"targets": ["couch", "sofa"], "related": []}',   # first target not accepted
    "find a mug on the desk": '{"targets": ["cup"], "related": ["desk", "sofa"]}',
    "find a lamp": '{"targets": ["Lamp"], "related": ["desk"]}',
}


class CheckReasoningTest(unittest.TestCase):
    def setUp(self):
        # No synonyms, so "couch" stays a model mistake the check must catch.
        self.cfg = MemoryGraphConfig(base_vocabulary=BASE, reasoning_timeout_s=1.0, class_synonyms=())
        self.encoder = WordEncoder()

    def expander(self, model):
        return ClassExpander(model, self.encoder, self.cfg)

    def test_the_written_set_loads(self):
        status, items = load_set(DEFAULT_SET)
        self.assertTrue(status)
        self.assertEqual(len({i.instruction for i in items}), len(items))
        for item in items:
            self.assertTrue(item.accept, item.instruction)
            self.assertEqual(item.accept, tuple(a.lower() for a in item.accept))

    def test_each_row_is_judged_on_its_first_target(self):
        rows = run_set(self.expander(ScriptedModel(REPLIES)), self.encoder, ITEMS, self.cfg)
        self.assertEqual([r["passed"] for r in rows], [True, False, True, True])
        self.assertEqual(rows[1]["targets"], ["couch", "sofa"])
        self.assertEqual(rows[2]["related_expected_found"], ["desk"])
        self.assertEqual(rows[3]["added"], ["lamp"])
        self.assertEqual({r["source"] for r in rows}, {"model"})

    def test_each_row_starts_from_the_base_vocabulary(self):
        """A class added by one row is new again in the next run of it."""
        expander = self.expander(ScriptedModel(REPLIES))
        first = run_set(expander, self.encoder, ITEMS, self.cfg)
        second = run_set(expander, self.encoder, ITEMS, self.cfg)
        self.assertEqual(first[3]["added"], second[3]["added"])

    def test_the_fall_back_alone_ranks_targets_best_first(self):
        rows = run_set(self.expander(None), self.encoder, ITEMS[:1], self.cfg)
        self.assertEqual((rows[0]["source"], rows[0]["why"]), ("fallback", "no model"))
        self.assertEqual(rows[0]["targets"][0], "chair")
        self.assertTrue(rows[0]["passed"])

    def test_the_round_trip_keeps_every_id(self):
        trip = round_trip(self.expander(ScriptedModel(REPLIES)), self.encoder, ITEMS, self.cfg)
        self.assertTrue(trip["passed"], trip["problems"])
        self.assertEqual(trip["added"], ["couch", "lamp"])
        self.assertEqual((trip["base"], trip["final"]), (5, 7))

    def test_expanders_are_built_one_at_a_time_and_reported(self):
        built = []

        def make(name, model):
            def build():
                built.append(name)
                return self.expander(model)
            return build

        runs = check({"stand-in": make("stand-in", ScriptedModel(REPLIES)), FALLBACK: make(FALLBACK, None)},
                     self.encoder, ITEMS, self.cfg)
        self.assertEqual(built, ["stand-in", FALLBACK])
        report = markdown("draft", runs)
        self.assertIn("3 of 4 pass. 4 answered by the model, 0 by the fall-back.", report)
        self.assertIn("| FAIL | find the couch |", report)
        self.assertIn("fallback: no model", report)
        with tempfile.TemporaryDirectory() as tmp:  # the report is plain JSON
            Path(tmp, "r.json").write_text(json.dumps(runs))


if __name__ == "__main__":
    unittest.main()
