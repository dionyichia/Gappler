"""The reasoning layer with the real models (T6.7b): Qwen for the reply, open_clip
for the task feature and the fall-back.

Needs torch, transformers, open_clip and both models' weights already on disk.
Without any of them the whole file is reported as skipped. Nothing is
downloaded here. Fetch the weights once with:
    python -m memory_graph.clip_encoder
    python -m memory_graph.reasoning "find a chair"
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

from memory_graph.config import MemoryGraphConfig

try:
    import open_clip  # noqa: F401
    import torch  # noqa: F401
    import transformers  # noqa: F401
    from huggingface_hub import try_to_load_from_cache
except ImportError as exc:  # pragma: no cover - depends on the machine
    raise unittest.SkipTest(f"needs open_clip, torch and transformers: {exc}")

from memory_graph.clip_encoder import OpenClipEncoder, cache_dir, weights_present
from memory_graph.reasoning import ClassExpander, QwenModel
from memory_graph.task import TaskContext
from memory_graph.vocabulary import Vocabulary

CFG = MemoryGraphConfig()
if not weights_present(CFG.clip_model, CFG.clip_pretrained):  # pragma: no cover
    raise unittest.SkipTest(
        f"no {CFG.clip_model} weights in {cache_dir()}: run python -m memory_graph.clip_encoder")
if not isinstance(try_to_load_from_cache(CFG.reasoning_model, "config.json"), str):  # pragma: no cover
    raise unittest.SkipTest(f"no {CFG.reasoning_model} weights in the Hugging Face cache")


class RealModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoder = OpenClipEncoder.from_config(CFG)
        cls.expander = ClassExpander(QwenModel(CFG), cls.encoder, CFG)

    def expand(self, instruction):
        vocab = Vocabulary.from_config(CFG)
        return self.expander.expand(TaskContext.from_text(instruction, self.encoder), vocab), vocab

    def test_find_a_chair(self):
        """The done-when: the model's own reply is used, within the time limit,
        and names the chair."""
        result, _ = self.expand("find a chair")
        self.assertEqual(result.source, "model", f"{result.why}, reply {result.reply!r}")
        self.assertIn("chair", result.task.targets)
        self.assertLess(result.seconds, CFG.reasoning_timeout_s)

    def test_related_classes_are_from_the_vocabulary(self):
        result, vocab = self.expand("bring me my laptop")
        for name in result.task.related:
            self.assertIn(name, vocab)
        self.assertTrue(result.task.targets)

    def test_a_reply_that_runs_out_of_time_falls_back(self):
        """A time limit far below what the model needs: the fall-back is used
        and the call returns close to the limit."""
        cfg = MemoryGraphConfig(reasoning_timeout_s=0.001)
        expander = ClassExpander(self.expander.model, self.encoder, cfg)
        result = expander.expand(TaskContext.from_text("find a chair", self.encoder), Vocabulary.from_config(cfg))
        expander._running.join(30.0)  # generate honours max_time, so this is quick. One call at a time.
        self.assertEqual(result.source, "fallback")
        self.assertIn("chair", result.task.targets)
        self.assertLess(result.seconds, 0.5)


if __name__ == "__main__":
    unittest.main()
