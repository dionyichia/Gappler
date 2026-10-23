"""T6.7's check: a written set of instructions through T6.7a to T6.7c together.

For every instruction in the set (memory_graph/eval/instructions_t6_7.json):

    task = TaskContext.from_text(instruction, encoder)      # T6.7a
    result = expander.expand(task, fresh base vocabulary)   # T6.7b, and T6.7c's extend_for_task

once per model and once with no model, so the CLIP fall-back alone. A row
passes if the first target is one the set accepts. Related classes are shown
for a person to judge, not scored.

Then the vocabulary round trip (T6.7c): every instruction in order on one
shared vocabulary, as a long run would see them. No phrase's class id may
change, and a save then a load must give the same list.

On the lab box, from the repo root (check the GPU is free first):

    .venv/bin/python -m memory_graph.check_reasoning --out <dir>

writes <dir>/check_reasoning.md, a table per model to check by hand, and
<dir>/check_reasoning.json with every raw reply.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from memory_graph.config import MemoryGraphConfig
from memory_graph.reasoning import ClassExpander, Expansion
from memory_graph.task import TaskContext, TextEncoder
from memory_graph.vocabulary import Vocabulary, normalise

DEFAULT_SET = Path(__file__).resolve().parent / "eval" / "instructions_t6_7.json"
DEFAULT_MODELS = ("Qwen/Qwen2.5-0.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct")
FALLBACK = "fallback only"


@dataclasses.dataclass(frozen=True)
class Item:
    instruction: str
    kind: str
    accept: tuple
    related_expected: tuple = ()


def load_set(path) -> tuple:
    """(status, items) from an instruction set file."""
    data = json.loads(Path(path).read_text())
    items = tuple(
        Item(d["instruction"], d.get("kind", ""), tuple(normalise(a) for a in d["accept"]),
             tuple(normalise(r) for r in d.get("related_expected", ())))
        for d in data["instructions"])
    if not items:
        raise ValueError(f"{path}: no instructions")
    return data.get("status", ""), items


def run_one(expander: ClassExpander, encoder: TextEncoder, item: Item, vocab: Vocabulary) -> Dict:
    """One instruction through T6.7a to T6.7c on `vocab`, judged against the set."""
    result: Expansion = expander.expand(TaskContext.from_text(item.instruction, encoder), vocab)
    targets = list(result.ranked)
    return {
        "instruction": item.instruction,
        "kind": item.kind,
        "source": result.source,
        "why": result.why,
        "targets": targets,
        "related": sorted(result.task.related),
        "added": list(result.added),
        "seconds": round(result.seconds, 3),
        "reply": result.reply,
        "accept": list(item.accept),
        "passed": bool(targets) and targets[0] in item.accept,
        "related_expected_found": [r for r in item.related_expected if r in result.task.related],
        "related_expected_missing": [r for r in item.related_expected if r not in result.task.related],
    }


def run_set(expander: ClassExpander, encoder: TextEncoder, items: Sequence[Item],
            cfg: MemoryGraphConfig) -> List[Dict]:
    """Every instruction on its own fresh copy of the base vocabulary."""
    return [run_one(expander, encoder, item, Vocabulary.from_config(cfg)) for item in items]


def round_trip(expander: ClassExpander, encoder: TextEncoder, items: Sequence[Item],
               cfg: MemoryGraphConfig) -> Dict:
    """Every instruction in order on one vocabulary. Reports any class id that
    changed, and whether a save then a load gives the same list."""
    vocab = Vocabulary.from_config(cfg)
    ids: Dict[str, int] = {p: i for i, p in enumerate(vocab)}
    problems: List[str] = []
    added: List[str] = []
    for item in items:
        result = expander.expand(TaskContext.from_text(item.instruction, encoder), vocab)
        added += result.added
        for phrase, class_id in ids.items():
            if vocab.id_of(phrase) != class_id:
                problems.append(f"after {item.instruction!r}: {phrase!r} moved from {class_id} to {vocab.id_of(phrase)}")
        ids.update({p: vocab.id_of(p) for p in result.added})
    if not vocab.starts_with(cfg.base_vocabulary):
        problems.append("the vocabulary no longer starts with the base list")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "vocabulary.json"
        vocab.save(path)
        if Vocabulary.load(path, base=cfg.base_vocabulary).phrases != vocab.phrases:
            problems.append("save then load changed the list")
    return {"base": len(cfg.base_vocabulary), "final": len(vocab), "added": added,
            "problems": problems, "passed": not problems}


def markdown(status: str, runs: Dict[str, Dict]) -> str:
    """The report: per model, a summary line, then one row per instruction."""
    lines = [f"# T6.7 reasoning check", "", f"Instruction set: {status or 'no status'}", ""]
    for name, run in runs.items():
        rows, trip = run["rows"], run["round_trip"]
        passed = sum(r["passed"] for r in rows)
        model_rows = sum(r["source"] == "model" for r in rows)
        lines += [f"## {name}", "",
                  f"{passed} of {len(rows)} pass. {model_rows} answered by the model, "
                  f"{len(rows) - model_rows} by the fall-back. "
                  f"Round trip: {'ids kept' if trip['passed'] else 'FAILED'}, "
                  f"{trip['base']} to {trip['final']} phrases.", ""]
        lines += [f"- {p}" for p in trip["problems"]]
        lines += ["| | Instruction | Kind | Source | Targets | Related | New | s |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            mark = "pass" if r["passed"] else "FAIL"
            source = r["source"] if not r["why"] else f"{r['source']}: {r['why']}"
            lines.append(f"| {mark} | {r['instruction']} | {r['kind']} | {source} | "
                         f"{', '.join(r['targets'])} | {', '.join(r['related'])} | "
                         f"{', '.join(r['added'])} | {r['seconds']:.2f} |")
        lines.append("")
    return "\n".join(lines)


def check(expanders: Dict[str, Callable[[], ClassExpander]], encoder: TextEncoder,
          items: Sequence[Item], cfg: MemoryGraphConfig) -> Dict[str, Dict]:
    """Run the set and the round trip with each expander. Each is built only
    when its turn comes, so one model at a time is loaded."""
    runs = {}
    for name, make in expanders.items():
        expander = make()
        runs[name] = {"rows": run_set(expander, encoder, items, cfg),
                      "round_trip": round_trip(expander, encoder, items, cfg)}
        del expander
        _free_gpu()
    return runs


def _free_gpu() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--set", default=str(DEFAULT_SET), help="instruction set file")
    ap.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    ap.add_argument("--out", required=True, help="folder for the report")
    args = ap.parse_args(argv)

    from memory_graph.clip_encoder import OpenClipEncoder
    from memory_graph.reasoning import QwenModel

    cfg = MemoryGraphConfig()
    status, items = load_set(args.set)
    encoder = OpenClipEncoder.from_config(cfg)

    def with_model(name: str) -> Callable[[], ClassExpander]:
        model_cfg = dataclasses.replace(cfg, reasoning_model=name)
        return lambda: ClassExpander(QwenModel(model_cfg), encoder, model_cfg)

    expanders = {name: with_model(name) for name in args.models}
    expanders[FALLBACK] = lambda: ClassExpander(None, encoder, cfg)
    runs = check(expanders, encoder, items, cfg)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = markdown(status, runs)
    (out / "check_reasoning.md").write_text(report + "\n")
    (out / "check_reasoning.json").write_text(json.dumps({"status": status, "runs": runs}, indent=1) + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
