"""The detector's class list, which only ever grows (T6.7c).

SAM 3 is prompted with every phrase of the vocabulary on every photo (S1,
sam3_adapter.detect). A detection's class id is its phrase's position in that
list. So the list must never be reordered or shortened, or class 5 would mean
one thing in an early photo and another thing later.

    vocab = Vocabulary.from_config(cfg)            # the base list, ids 0 to 29
    task, new = extend_for_task(vocab, task)       # the task's classes, appended
    dets = detect(segmenter, rgb, vocab)           # every phrase, ids as above

Upstream keeps this list in ObjectClasses (map/map_elements.py:330). Its ids can
change between runs and within one: the base list is built from a set
(map_elements.py:368), whose order Python changes from run to run, and extra
classes are added through a set difference, in no fixed order
(map_elements.py:405). Here the base comes from config in a fixed order, and
new phrases are appended in the order they are given.

Phrases are compared after normalising: trimmed, lower case, inner spaces
collapsed. "Chair" and " chair" are one class, "chair", and the normalised
spelling is the label every detection gets. Background classes are never
added: S2 drops them, so prompting them would cost a SAM 3 query for nothing.

save and load keep the list in a JSON file, so a replay of a recording uses
the same ids as the run that recorded it.

No numpy, no torch: stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

if TYPE_CHECKING:  # only for the type hints, so this module stays stdlib-only
    from memory_graph.config import MemoryGraphConfig
    from memory_graph.stage_types import Detections
    from memory_graph.task import TaskContext

FILE_VERSION = 1


def normalise(phrase: str) -> str:
    """The spelling a phrase is stored and compared under."""
    return " ".join(str(phrase).split()).lower()


class Vocabulary(Sequence[str]):
    """An ordered list of phrases. A phrase's position is its class id.

    It is a Sequence, so it can go wherever a list of phrases goes, for example
    to sam3_adapter.detect.
    """

    def __init__(self, phrases: Iterable[str] = (), background: Iterable[str] = ()) -> None:
        self._background = frozenset(normalise(b) for b in background)
        self._phrases: List[str] = []
        self._ids: dict = {}
        base = [normalise(p) for p in phrases]
        repeated = sorted({p for p in base if base.count(p) > 1})
        if repeated:
            raise ValueError(f"the base list repeats {repeated}")
        bad = sorted(set(base) & self._background)
        if bad:
            raise ValueError(f"the base list has background classes {bad}")
        self.add(base)

    @classmethod
    def from_config(cls, cfg: "MemoryGraphConfig") -> "Vocabulary":
        """cfg.base_vocabulary, with cfg.bg_classes kept out if cfg.skip_bg."""
        return cls(cfg.base_vocabulary, cfg.bg_classes if cfg.skip_bg else ())

    # ---------------------------------------------------------------- read

    def __len__(self) -> int:
        return len(self._phrases)

    def __getitem__(self, index):
        """The phrase with class id `index`, or a list for a slice."""
        return self._phrases[index]

    def __iter__(self) -> Iterator[str]:
        return iter(self._phrases)

    def __contains__(self, phrase: object) -> bool:
        return isinstance(phrase, str) and normalise(phrase) in self._ids

    @property
    def phrases(self) -> Tuple[str, ...]:
        return tuple(self._phrases)

    @property
    def background(self) -> frozenset:
        return self._background

    def id_of(self, phrase: str) -> int:
        """The class id of a phrase. KeyError if it is not in the list."""
        key = normalise(phrase)
        if key not in self._ids:
            raise KeyError(f"{phrase!r} is not in the vocabulary")
        return self._ids[key]

    def phrase_of(self, class_id: int) -> str:
        """The phrase with this class id. KeyError if there is none."""
        if not 0 <= class_id < len(self._phrases):
            raise KeyError(f"no class id {class_id}, the vocabulary has {len(self._phrases)} phrases")
        return self._phrases[class_id]

    def starts_with(self, phrases: Sequence[str]) -> bool:
        """True if this list begins with `phrases`, in that order. A list that
        grew from that base gives the base's phrases the same ids."""
        base = [normalise(p) for p in phrases]
        return self._phrases[: len(base)] == base

    def check_detections(self, dets: "Detections") -> List[str]:
        """Every detection whose class id and label disagree with this list.
        Empty when all agree."""
        problems = []
        for i, (class_id, label) in enumerate(zip(dets.class_id, dets.label)):
            class_id = int(class_id)
            if not 0 <= class_id < len(self._phrases):
                problems.append(f"detection {i}: class id {class_id} is not in the vocabulary")
            elif self._phrases[class_id] != label:
                problems.append(
                    f"detection {i}: class id {class_id} is {self._phrases[class_id]!r}, "
                    f"the label is {label!r}"
                )
        return problems

    # ---------------------------------------------------------------- grow

    def add(self, phrases: Iterable[str]) -> List[str]:
        """Append the phrases not already in the list, in the order given.
        Returns the ones appended, normalised. A phrase already in the list, a
        repeat within `phrases` and a background class are skipped. An empty
        phrase is an error."""
        added = []
        for phrase in phrases:
            key = normalise(phrase)
            if not key:
                raise ValueError("a vocabulary phrase cannot be empty")
            if key in self._ids or key in self._background:
                continue
            self._ids[key] = len(self._phrases)
            self._phrases.append(key)
            added.append(key)
        return added

    # ---------------------------------------------------------------- file

    def save(self, path: Union[str, Path]) -> None:
        """Write the list to a JSON file, in id order."""
        data = {"version": FILE_VERSION, "phrases": self._phrases, "background": sorted(self._background)}
        Path(path).write_text(json.dumps(data, indent=1) + "\n")

    @classmethod
    def load(cls, path: Union[str, Path], base: Optional[Sequence[str]] = None) -> "Vocabulary":
        """Read a list written by save. If `base` is given, the file must start
        with it, so a run's base ids still mean the same phrases."""
        data = json.loads(Path(path).read_text())
        if data.get("version") != FILE_VERSION:
            raise ValueError(f"{path}: vocabulary file version {data.get('version')!r}, expected {FILE_VERSION}")
        vocab = cls(data["phrases"], data.get("background", ()))
        if base is not None and not vocab.starts_with(base):
            raise ValueError(f"{path}: the saved vocabulary does not start with the base list, so its ids differ")
        return vocab


def extend_for_task(vocab: Vocabulary, task: "TaskContext") -> Tuple["TaskContext", List[str]]:
    """The round trip's first half: add the task's target and related classes
    to the vocabulary, so the detector is prompted with them from the next
    photo on. Upstream: Map.add_target_class (map/map.py:159).

    Returns the task with its classes in the vocabulary's spelling, and the
    phrases that were new. Pass that task on (ObjectStore.set_task): detections
    are labelled with the normalised spelling, so a task that kept "Chair"
    would never match an object labelled "chair". A background class in the
    task stays in the task but is not added to the vocabulary.
    """
    targets = [normalise(c) for c in sorted(task.targets)]
    related = [normalise(c) for c in sorted(task.related)]
    new = vocab.add(targets + related)
    return task.with_classes(targets, related), new
