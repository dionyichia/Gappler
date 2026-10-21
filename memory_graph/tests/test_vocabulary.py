"""The vocabulary that only grows (T6.7c, memory_graph/vocabulary.py).

Done-when: classes added in different orders, and a save then a load, never
change an existing id, and detections from a stand-in SAM 3 carry the ids of
their labels. The core tests need only the standard library. The ones that use
detect or TaskContext need numpy, and skip without it.
"""

import json
import tempfile
import unittest
from pathlib import Path

from memory_graph.config import MemoryGraphConfig
from memory_graph.vocabulary import Vocabulary, extend_for_task, normalise

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on the machine
    np = None

BASE = ("chair", "table", "cup")
BG = ("wall", "floor")


def make_task(targets, related=()):
    from memory_graph.task import TaskContext  # needs numpy
    return TaskContext("find a chair", np.array([1.0, 0.0]), frozenset(targets), frozenset(related))


class NormaliseTest(unittest.TestCase):
    def test_case_and_spaces(self):
        self.assertEqual(normalise("  Power   Outlet "), "power outlet")
        self.assertEqual(normalise("tv_monitor"), "tv_monitor")


class IdsTest(unittest.TestCase):
    def test_a_phrase_id_is_its_position(self):
        vocab = Vocabulary(BASE)
        self.assertEqual([vocab.id_of(p) for p in BASE], [0, 1, 2])
        self.assertEqual([vocab.phrase_of(i) for i in range(3)], list(BASE))
        self.assertEqual(list(vocab), list(BASE))
        self.assertEqual(vocab[1], "table")

    def test_lookups_ignore_case_and_spaces(self):
        vocab = Vocabulary(BASE)
        self.assertEqual(vocab.id_of(" Table "), 1)
        self.assertIn("CUP", vocab)
        self.assertNotIn("sofa", vocab)

    def test_unknown_phrase_or_id_is_an_error(self):
        vocab = Vocabulary(BASE)
        with self.assertRaises(KeyError):
            vocab.id_of("sofa")
        for bad in (-1, 3):
            with self.assertRaises(KeyError):
                vocab.phrase_of(bad)


class AddTest(unittest.TestCase):
    def test_new_phrases_are_appended_in_the_order_given(self):
        vocab = Vocabulary(BASE)
        self.assertEqual(vocab.add(["sofa", "Lamp"]), ["sofa", "lamp"])
        self.assertEqual(vocab.phrases, BASE + ("sofa", "lamp"))

    def test_existing_ids_never_change_whatever_the_order(self):
        # the done-when, first half
        for order in (["sofa", "lamp", "bottle"], ["bottle", "sofa", "lamp"], ["lamp", "bottle", "sofa"]):
            vocab = Vocabulary(BASE)
            vocab.add(order[:2])
            vocab.add(order[1:])                      # one phrase again, one new
            self.assertEqual([vocab.id_of(p) for p in BASE], [0, 1, 2])
            self.assertEqual(vocab.phrases[3:], tuple(order))

    def test_a_phrase_added_twice_or_in_another_case_gets_no_new_id(self):
        vocab = Vocabulary(BASE)
        self.assertEqual(vocab.add(["Chair", "sofa", "SOFA", " sofa"]), ["sofa"])
        self.assertEqual(len(vocab), 4)

    def test_background_classes_are_never_added(self):
        vocab = Vocabulary(BASE, background=BG)
        self.assertEqual(vocab.add(["Floor", "sofa"]), ["sofa"])
        self.assertNotIn("floor", vocab)

    def test_an_empty_phrase_is_an_error(self):
        with self.assertRaises(ValueError):
            Vocabulary(BASE).add(["  "])

    def test_a_bad_base_list_is_an_error(self):
        with self.assertRaises(ValueError):
            Vocabulary(["chair", "Chair"])
        with self.assertRaises(ValueError):
            Vocabulary(["chair", "wall"], background=BG)

    def test_starts_with(self):
        vocab = Vocabulary(BASE)
        vocab.add(["sofa"])
        self.assertTrue(vocab.starts_with(BASE))
        self.assertFalse(vocab.starts_with(("table", "chair")))


class FromConfigTest(unittest.TestCase):
    def test_the_base_list_and_the_background_come_from_config(self):
        cfg = MemoryGraphConfig()
        vocab = Vocabulary.from_config(cfg)
        self.assertEqual(vocab.phrases, cfg.base_vocabulary)
        self.assertEqual(vocab.add(["wall"]), [])

    def test_background_is_allowed_when_skip_bg_is_off(self):
        vocab = Vocabulary.from_config(MemoryGraphConfig(skip_bg=False))
        self.assertEqual(vocab.add(["wall"]), ["wall"])


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "vocabulary.json"

    def test_save_then_load_keeps_every_id(self):
        # the done-when, second half
        vocab = Vocabulary(BASE, background=BG)
        vocab.add(["sofa", "lamp"])
        vocab.save(self.path)
        again = Vocabulary.load(self.path, base=BASE)
        self.assertEqual(again.phrases, vocab.phrases)
        self.assertEqual(again.background, vocab.background)
        self.assertEqual(again.add(["sofa", "bottle"]), ["bottle"])
        self.assertEqual(again.id_of("bottle"), 5)

    def test_a_file_from_another_base_list_is_refused(self):
        Vocabulary(("table", "chair")).save(self.path)
        with self.assertRaises(ValueError):
            Vocabulary.load(self.path, base=BASE)

    def test_an_unknown_file_version_is_refused(self):
        self.path.write_text(json.dumps({"version": 99, "phrases": ["chair"]}))
        with self.assertRaises(ValueError):
            Vocabulary.load(self.path)


@unittest.skipIf(np is None, "needs numpy")
class TaskTest(unittest.TestCase):
    def test_the_task_classes_are_appended_and_spelled_as_the_vocabulary(self):
        vocab = Vocabulary(BASE, background=BG)
        task, new = extend_for_task(vocab, make_task({"Office Chair", "chair"}, {"Desk Lamp", "floor"}))
        self.assertEqual(new, ["office chair", "desk lamp"])          # targets first, then related
        self.assertEqual(task.targets, {"chair", "office chair"})
        self.assertEqual(task.related, {"desk lamp", "floor"})       # floor stays in the task
        self.assertNotIn("floor", vocab)
        self.assertEqual(task.instruction, "find a chair")

    def test_the_same_task_twice_adds_nothing(self):
        vocab = Vocabulary(BASE)
        extend_for_task(vocab, make_task({"sofa"}))
        self.assertEqual(extend_for_task(vocab, make_task({"sofa"}))[1], [])
        self.assertEqual(len(vocab), 4)

    def test_order_does_not_depend_on_set_order(self):
        # the classes come in a frozenset, which has no order, so they are sorted first
        a, b = Vocabulary(BASE), Vocabulary(BASE)
        extend_for_task(a, make_task({"sofa", "lamp", "bottle"}))
        extend_for_task(b, make_task({"bottle", "lamp", "sofa"}))
        self.assertEqual(a.phrases, b.phrases)


@unittest.skipIf(np is None, "needs numpy")
class DetectTest(unittest.TestCase):
    """The round trip's second half: the detector is prompted with the whole list."""

    def setUp(self):
        from memory_graph.tests.test_sam3_adapter import CUP, TABLE, FakeBatchedSam3, FakeSam3, found
        self.results = {"table": found((TABLE, 0.9)), "sofa": found((CUP, 0.8))}
        self.fakes = (FakeSam3, FakeBatchedSam3)
        self.rgb = np.zeros((60, 80, 3), dtype=np.uint8)

    def test_detections_carry_the_ids_of_their_labels(self):
        from memory_graph.sam3_adapter import detect
        for fake in self.fakes:
            vocab = Vocabulary(BASE)
            vocab.add(["sofa"])
            dets = detect(fake(self.results), self.rgb, vocab)
            self.assertEqual(dets.label, ["table", "sofa"])
            self.assertEqual(list(dets.class_id), [vocab.id_of("table"), vocab.id_of("sofa")])
            self.assertEqual(vocab.check_detections(dets), [])

    def test_a_new_class_is_prompted_from_the_next_photo(self):
        from memory_graph.sam3_adapter import detect
        sam, vocab = self.fakes[1](self.results), Vocabulary(BASE)
        detect(sam, self.rgb, vocab)
        extend_for_task(vocab, make_task({"sofa"}))
        detect(sam, self.rgb, vocab)
        self.assertEqual([p for _, p in sam.batch_calls], [list(BASE), list(BASE) + ["sofa"]])

    def test_check_detections_finds_a_mismatch(self):
        from memory_graph.stage_types import Detections
        dets = Detections(xyxy=np.zeros((2, 4)), conf=np.ones(2), class_id=np.array([1, 7]), label=["cup", "chair"])
        problems = Vocabulary(BASE).check_detections(dets)
        self.assertEqual(len(problems), 2)
        self.assertIn("'table'", problems[0])
        self.assertIn("class id 7", problems[1])


if __name__ == "__main__":
    unittest.main()
