"""The reasoning layer's model call (T6.7b): an instruction in, classes out.

Once, at the start of a task, a small local text model reads the instruction
and the vocabulary and names two sets of classes:

    targets   what the instruction asks for, "find a chair" -> chair
    related   classes likely to be near a target, chair -> table, desk

    expander = ClassExpander(QwenModel(cfg), encoder, cfg)
    result = expander.expand(TaskContext.from_text("find a chair", encoder), vocab)
    store.set_task(result.task)                    # targets and related filled in
    dets = detect(segmenter, rgb, vocab)           # new targets prompted from here on

Upstream is VLM.parse_target_objects (vlm/vlm.py:55) with the prompt from
format_prefiltering_prompt (vlm/vlm_offline.py:69). Four differences:

- The reply is one JSON object, not four lines. A small model drifts from a
  line count, and JSON can be found inside a chatty reply.
- The call has a time limit. Upstream waits for as long as the model takes, so
  one stuck reply hangs the task.
- When the reply is unusable, the fall-back is upstream's CLIP rule
  (Map.set_target_object_with_clip, map/map.py:193), which upstream has but
  calls elsewhere. Upstream makes every class it keeps a target. Here only the
  best is, and the rest are related (T6.7).
- A name that means a class already in the list is read as that class
  (config class_synonyms), and "_" matches a space (T6.7).

As upstream, related classes must already be in the vocabulary (vlm.py:96), and
a target may be new: that is how the vocabulary grows (T6.7c, extend_for_task).

The prompt, the parser and the time limit need only the standard library. The
fall-back and TaskContext need numpy, QwenModel needs torch and transformers.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, Sequence, Tuple

from memory_graph.vocabulary import Vocabulary, extend_for_task, name_key, normalise

if TYPE_CHECKING:  # only for the type hints, so the parser stays stdlib-only
    from memory_graph.config import MemoryGraphConfig
    from memory_graph.task import TaskContext, TextEncoder

Message = Dict[str, str]

SYSTEM_PROMPT = "You are the planner of a robot that searches a building for objects."

# Upstream's prompt, cut down for a small model: two examples, a JSON reply. The
# second example and the "2 to 5" come from T6.7's check: 1.5B added "couch" as a
# new class with sofa in the list, and named related classes for 1 instruction of 22
# while the prompt said "Leave it empty if none are".
PROMPT = """Read the instruction and pick object classes for the search.

"targets": the object the instruction asks for. If a name in the list means the same \
thing, use that name. If none fits, give a short common name for it.
"related": 2 to 5 objects from the list that are often near the target, most useful \
first. Use only names from the list.

Reply with one JSON object and nothing else.

Example. Instruction: "get me a pen"
{{"targets": ["pen"], "related": ["desk", "table", "cup"]}}

Example, with sofa in the list. Instruction: "find the couch"
{{"targets": ["sofa"], "related": ["cushion", "table"]}}

List: {classes}

Instruction: "{instruction}"
"""

# A class name is a few plain words. Anything else is the model rambling, and
# every name added to the vocabulary costs a SAM 3 query on every photo.
MAX_WORDS = 4
_NAME = re.compile(r"^[a-z0-9][a-z0-9 _'-]*$")


def build_messages(instruction: str, vocab: Sequence[str]) -> List[Message]:
    """The chat messages for one instruction, the vocabulary listed in id order."""
    user = PROMPT.format(classes=", ".join(vocab), instruction=" ".join(str(instruction).split()))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def _first_json_object(reply: str) -> Optional[dict]:
    """The first JSON object anywhere in the reply, or None. Finds it inside
    code fences or surrounding prose."""
    decoder = json.JSONDecoder()
    for start in (i for i, ch in enumerate(reply) if ch == "{"):
        try:
            value, _ = decoder.raw_decode(reply, start)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _names(value) -> List[str]:
    """A list of names from a JSON list, or from one comma-separated string."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list):
        return []
    return [normalise(v) for v in value if isinstance(v, str)]


def _is_name(name: str) -> bool:
    return bool(_NAME.match(name)) and len(name.split()) <= MAX_WORDS


@dataclass(frozen=True)
class ParsedReply:
    targets: Tuple[str, ...]
    related: Tuple[str, ...]


def parse_reply(
    reply: Optional[str],
    vocab: Vocabulary,
    max_targets: int = 3,
    max_related: int = 5,
    synonyms: Sequence[Tuple[str, str]] = (),
) -> Tuple[Optional[ParsedReply], str]:
    """Read the model's reply. Returns (classes, "") if it is usable, else
    (None, why it is not).

    Names are put in the vocabulary's spelling, with "_" and a space read alike
    ("tv monitor" is tv_monitor), and a name in `synonyms` (name, list class)
    becomes that class ("couch" is sofa). A name not in the list is kept with
    spaces ("fire_extinguisher" becomes fire extinguisher). A name that is not a short
    plain phrase, a background class, or a repeat is dropped. A related name
    must already be in the vocabulary (upstream, vlm.py:96), and a name that is
    a target is not also related. The reply is usable if one target is left.
    Each list is cut to its maximum, keeping the model's order.
    """
    if not reply or not reply.strip():
        return None, "empty reply"
    obj = _first_json_object(reply)
    if obj is None:
        return None, "no JSON object in the reply"
    spelling = {name_key(p): p for p in vocab}
    renamed = {name_key(name): name_key(cls) for name, cls in synonyms}

    def canonical(name: str) -> str:
        key = name_key(name)
        key = renamed.get(key, key)
        return spelling.get(key, key)

    raw_targets = [canonical(n) for n in _names(obj.get("targets", obj.get("target")))]
    raw_related = [canonical(n) for n in _names(obj.get("related", obj.get("relevant")))]

    def keep(names: List[str], seen: set, in_vocab_only: bool, limit: int) -> List[str]:
        kept = []
        for name in names:
            if len(kept) == limit:
                break
            if name in seen or name in vocab.background or not _is_name(name):
                continue
            if in_vocab_only and name not in vocab:
                continue
            seen.add(name)
            kept.append(name)
        return kept

    seen: set = set()
    targets = keep(raw_targets, seen, False, max_targets)
    if not targets:
        return None, "no usable target in the reply"
    related = keep(raw_related, seen, True, max_related)
    return ParsedReply(tuple(targets), tuple(related)), ""


def fallback_targets(
    task: "TaskContext",
    vocab: Sequence[str],
    encoder: "TextEncoder",
    ratio: float = 0.95,
    top_k: int = 5,
) -> List[str]:
    """Upstream's rule when the model gives nothing (map/map.py:193): the
    vocabulary classes whose text similarity to the instruction is within
    `ratio` of the best, best first, at most top_k. Ties keep vocabulary order.

    The threshold is best - (1 - ratio) * |best|, which is upstream's
    ratio * best when best is positive and still keeps the best class when it
    is not.
    """
    import numpy as np

    phrases = list(vocab)
    if not phrases:
        return []
    feats = np.asarray(encoder.encode_text(phrases), dtype=np.float64)
    norms = np.linalg.norm(feats, axis=1)
    sims = np.where(norms > 0, feats @ task.feature / np.where(norms > 0, norms, 1.0), 0.0)
    best = float(sims.max())
    threshold = best - (1.0 - ratio) * abs(best)
    order = sorted(range(len(phrases)), key=lambda i: (-sims[i], i))
    return [phrases[i] for i in order if sims[i] >= threshold][:top_k]


class ReplyModel(Protocol):
    def reply(self, messages: List[Message], max_new_tokens: int, max_time: float) -> str:
        """The model's answer to a chat, as text. max_time is seconds."""
        ...


@dataclass(frozen=True)
class Expansion:
    """What expand did. `task` is the one to pass on (ObjectStore.set_task)."""

    task: "TaskContext"
    source: str                      # "model" or "fallback"
    why: str = ""                    # why the fall-back was used, "" for "model"
    reply: Optional[str] = None      # the raw reply, None if there was none
    added: Tuple[str, ...] = ()      # phrases appended to the vocabulary
    seconds: float = 0.0             # time spent waiting for the model
    ranked: Tuple[str, ...] = ()     # the targets best first: the model's order, or the fall-back's


class ClassExpander:
    """Instruction -> target and related classes, with a time limit and the
    CLIP fall-back. One model call at a time: the model is not thread-safe, so
    while an earlier call that ran out of time is still generating, a new task
    goes straight to the fall-back."""

    def __init__(self, model: Optional[ReplyModel], encoder: "TextEncoder", cfg: "MemoryGraphConfig") -> None:
        self.model = model
        self.encoder = encoder
        self.cfg = cfg
        self._running: Optional[threading.Thread] = None

    def _ask(self, messages: List[Message]) -> Tuple[Optional[str], str, float]:
        """(reply, why it failed, seconds). The call runs in a daemon thread,
        so a stuck model cannot hang the task or stop the process exiting.
        max_time is passed on too, so a model that honours it stops by itself."""
        if self.model is None:
            return None, "no model", 0.0
        if self._running is not None and self._running.is_alive():
            return None, "the previous model call is still running", 0.0
        timeout = self.cfg.reasoning_timeout_s
        box: dict = {}

        def call() -> None:
            try:
                box["reply"] = self.model.reply(messages, self.cfg.reasoning_max_new_tokens, timeout)
            except Exception as exc:  # any model failure means: use the fall-back
                box["error"] = f"{type(exc).__name__}: {exc}"

        start = time.monotonic()
        self._running = threading.Thread(target=call, name="class-expander", daemon=True)
        self._running.start()
        self._running.join(timeout)
        seconds = time.monotonic() - start
        if self._running.is_alive():
            return None, f"no reply within {timeout:g} s", seconds
        if "error" in box:
            return None, f"the model failed: {box['error']}", seconds
        return box.get("reply"), "", seconds

    def expand(self, task: "TaskContext", vocab: Vocabulary) -> Expansion:
        """Fill in the task's targets and related classes and append new
        targets to the vocabulary (extend_for_task). The task's own classes,
        if it had any, are replaced."""
        reply, why, seconds = self._ask(build_messages(task.instruction, vocab))
        parsed = None
        if not why:
            parsed, why = parse_reply(reply, vocab, self.cfg.reasoning_max_targets,
                                      self.cfg.reasoning_max_related, self.cfg.class_synonyms)
        if parsed is not None:
            source, targets, related = "model", parsed.targets, parsed.related
        else:
            # The best class is the target, the rest of upstream's list is related
            # (config: fallback_ratio).
            source = "fallback"
            ranked = fallback_targets(task, vocab, self.encoder,
                                      self.cfg.fallback_ratio, self.cfg.fallback_top_k)
            targets, related = ranked[:1], ranked[1:1 + self.cfg.reasoning_max_related]
        new_task, added = extend_for_task(vocab, task.with_classes(targets, related))
        ranked = tuple(normalise(t) for t in targets)
        return Expansion(new_task, source, why, reply, tuple(added), seconds, ranked)


class QwenModel:
    """A local chat model through transformers, loaded as the voice path loads
    it (aria/aria_app/services/prompt_extractor.py:32). Greedy decoding, so the
    same instruction gives the same reply."""

    def __init__(self, cfg: "MemoryGraphConfig") -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = cfg.reasoning_device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(cfg.reasoning_model)
        # float16 on the GPU, as the voice path. On a CPU float16 is slow or missing.
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(cfg.reasoning_model, dtype=dtype)
        self.model.to(device)
        self.model.eval()

    def reply(self, messages: List[Message], max_new_tokens: int, max_time: float) -> str:
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        with self._torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                max_time=max_time,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


if __name__ == "__main__":  # python -m memory_graph.reasoning "find a chair" ...
    import sys

    from memory_graph.clip_encoder import OpenClipEncoder
    from memory_graph.config import MemoryGraphConfig
    from memory_graph.task import TaskContext

    cfg = MemoryGraphConfig()
    encoder = OpenClipEncoder.from_config(cfg)
    expander = ClassExpander(QwenModel(cfg), encoder, cfg)
    for instruction in sys.argv[1:] or ["find a chair"]:
        result = expander.expand(TaskContext.from_text(instruction, encoder), Vocabulary.from_config(cfg))
        print(f"{instruction!r}: {result.source} in {result.seconds:.2f} s {result.why}".rstrip())
        print(f"  targets {sorted(result.task.targets)}  related {sorted(result.task.related)}")
        print(f"  reply {result.reply!r}")
