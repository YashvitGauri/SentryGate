"""Make the Week 4 attack set from two public datasets.

Output, all under data/week4/:

    seeds.jsonl      the attacks we start from, one per line
    variants.jsonl   rewordings of each seed, tagged by family and method
    controls.jsonl   honest questions, to see if normal users hit poison too
    manifest.json    where every input came from, with file hashes

Two families of rewording, kept apart everywhere, because Phase 1 showed they
behave completely differently:

    lazy     fixed rules: capitals, a full stop, "please", a typo.
             Free for an attacker. No model, no skill.
    rewrite  real paraphrases from a local T5 model.

Plus one "exact" variant per seed, the seed text itself. It must always hit,
so it is a check that the experiment works, not a result.

Everything is deterministic: fixed random seeds, rule-based edits, and beam
search (no sampling) for the paraphrases. The output is committed, so the
sweep can be rerun without the 900 MB paraphrase model.

Run inside the attacks image:   make variants
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "week4"
RAW = OUT / "raw"

PARQUET = "https://huggingface.co/datasets/{name}/resolve/refs%2Fconvert%2Fparquet/default/{split}/0000.parquet"
SOURCES = [
    ("deepset/prompt-injections", "train"),
    ("deepset/prompt-injections", "test"),
    ("jayavibhav/prompt-injection", "test"),
]
PARAPHRASER = "humarin/chatgpt_paraphraser_on_T5_base"

RANDOM_SEED = 20260919
JAY_SEEDS = 100
CONTROLS = 100
MIN_CHARS, MAX_CHARS = 20, 400
REWRITES_PER_SEED = 3

# deepset mixes English and German. MiniLM is an English model, so a German
# seed would measure the embedder's German, not the bypass. Counting common
# words is crude, but it is simple, visible and deterministic.
_EN = re.compile(r"\b(the|you|and|your|to|is|of|a|what|all|now|ignore|please)\b", re.I)
_DE = re.compile(r"\b(und|der|die|das|ich|nicht|mit|ist|sie|ein|eine|wie|was|bitte|alle)\b", re.I)


def looks_english(text: str) -> bool:
    return len(_EN.findall(text)) > len(_DE.findall(text))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(name: str, split: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name.replace('/', '__')}__{split}.parquet"
    if not path.exists():
        url = PARQUET.format(name=name, split=split)
        print(f"  downloading {name} [{split}]")
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    return path


def read_rows(path: Path) -> list[tuple[str, int]]:
    import pyarrow.parquet as pq

    table = pq.read_table(path).to_pydict()
    return [(str(t).strip(), int(label)) for t, label in zip(table["text"], table["label"])]


def keep(text: str) -> bool:
    return MIN_CHARS <= len(text) <= MAX_CHARS


def unique(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


# ---------------------------------------------------------------- lazy edits
# Each takes a seed and returns one edited copy. Every one is something a
# person does with a keyboard in under a second.

def _flip_first_case(text: str) -> str:
    first = text[0]
    return (first.lower() if first.isupper() else first.upper()) + text[1:]


def _toggle_full_stop(text: str) -> str:
    return text.rstrip(".!? ") if text.rstrip()[-1:] in ".!?" else text.rstrip() + "."


def _exclaim(text: str) -> str:
    return text.rstrip(".!? ") + "!!"


def _please_prefix(text: str) -> str:
    return "please " + text[0].lower() + text[1:]


def _please_suffix(text: str) -> str:
    return text.rstrip(".!? ") + " please"


def _double_space(text: str) -> str:
    spaces = [i for i, c in enumerate(text) if c == " "]
    if not spaces:
        return text + " "
    middle = spaces[len(spaces) // 2]
    return text[:middle] + " " + text[middle:]


def _all_caps(text: str) -> str:
    return text.upper()


def _typo(text: str) -> str:
    """Swap two letters in the middle of the longest word."""
    words = list(re.finditer(r"[A-Za-z]{4,}", text))
    if not words:
        return text + "x"
    word = max(words, key=lambda m: (len(m.group()), -m.start()))
    i = word.start() + len(word.group()) // 2 - 1
    return text[:i] + text[i + 1] + text[i] + text[i + 2:]


def _strip_punctuation(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text)).strip()


LAZY_EDITS = [
    ("flip_first_case", _flip_first_case),
    ("toggle_full_stop", _toggle_full_stop),
    ("exclaim", _exclaim),
    ("please_prefix", _please_prefix),
    ("please_suffix", _please_suffix),
    ("double_space", _double_space),
    ("all_caps", _all_caps),
    ("typo", _typo),
    ("strip_punctuation", _strip_punctuation),
]


# ------------------------------------------------------------------ rewrites

class Paraphraser:
    """Local T5 paraphraser, run with plain beam search.

    The model card uses group beam search for more varied output. Recent
    transformers only allows that with trust_remote_code=True, which would
    download and run code from the Hub at generation time. We do not turn that
    on. Plain beam search is deterministic and needs no remote code.
    """

    def __init__(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(PARAPHRASER)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(PARAPHRASER)
        self.model.eval()

    def rewrite(self, text: str, n: int) -> list[str]:
        import torch

        ids = self.tokenizer(f"paraphrase: {text}", return_tensors="pt",
                             max_length=128, truncation=True).input_ids
        with torch.no_grad():
            out = self.model.generate(
                ids, num_beams=5, num_return_sequences=n, repetition_penalty=10.0,
                no_repeat_ngram_size=2, max_length=128,
            )
        return self.tokenizer.batch_decode(out, skip_special_tokens=True)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rewrites", action="store_true", help="skip the paraphrase model (quick check)")
    args = ap.parse_args()

    print("Week 4 variants")
    files = {f"{n} [{s}]": download(n, s) for n, s in SOURCES}
    deepset = read_rows(files["deepset/prompt-injections [train]"]) + \
        read_rows(files["deepset/prompt-injections [test]"])
    jay = read_rows(files["jayavibhav/prompt-injection [test]"])

    rng = random.Random(RANDOM_SEED)
    deepset_attacks = unique([t for t, label in deepset if label == 1 and keep(t) and looks_english(t)])
    jay_pool = unique([t for t, label in jay if label == 1 and keep(t)])
    jay_attacks = rng.sample(jay_pool, JAY_SEEDS)
    honest_pool = unique([t for t, label in deepset if label == 0 and keep(t) and looks_english(t)])
    controls = rng.sample(honest_pool, min(CONTROLS, len(honest_pool)))

    seeds = [{"seed_id": f"deepset-{i:03d}", "dataset": "deepset", "text": t}
             for i, t in enumerate(deepset_attacks)]
    seeds += [{"seed_id": f"jay-{i:03d}", "dataset": "jayavibhav", "text": t}
              for i, t in enumerate(jay_attacks)]
    print(f"  seeds: {len(deepset_attacks)} deepset (all English attacks), "
          f"{len(jay_attacks)} jayavibhav (random, seed {RANDOM_SEED})")

    paraphraser = None if args.no_rewrites else Paraphraser()
    variants = []
    started = time.time()
    for n, seed in enumerate(seeds, 1):
        text, made = seed["text"], {norm(seed["text"])}
        exact_texts = {text}

        def add(family: str, method: str, variant: str) -> None:
            variants.append({
                "variant_id": f"{seed['seed_id']}-{family}-{method}",
                "seed_id": seed["seed_id"], "dataset": seed["dataset"],
                "family": family, "method": method, "text": variant,
            })

        add("exact", "same_text", text)
        for method, edit in LAZY_EDITS:
            variant = edit(text)
            # all_caps and flip_first_case differ from the seed only in case.
            # They are kept on purpose: whether case matters is part of the finding.
            if variant not in exact_texts:
                exact_texts.add(variant)
                add("lazy", method, variant)
        if paraphraser is not None:
            for i, variant in enumerate(paraphraser.rewrite(text, REWRITES_PER_SEED)):
                if variant.strip() and norm(variant) not in made:
                    made.add(norm(variant))
                    add("rewrite", f"t5_beam_{i}", variant.strip())
        if n % 25 == 0 or n == len(seeds):
            print(f"  {n}/{len(seeds)} seeds  ({time.time() - started:.0f}s)")

    OUT.mkdir(parents=True, exist_ok=True)

    def dump(name: str, rows: list[dict]) -> None:
        with open(OUT / name, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    dump("seeds.jsonl", seeds)
    dump("variants.jsonl", variants)
    dump("controls.jsonl", [{"control_id": f"control-{i:03d}", "text": t} for i, t in enumerate(controls)])

    counts: dict[str, int] = {}
    for v in variants:
        counts[v["family"]] = counts.get(v["family"], 0) + 1
    manifest = {
        "random_seed": RANDOM_SEED,
        "sources": {k: {"file": str(p.relative_to(ROOT)), "sha256": sha256(p)} for k, p in files.items()},
        "paraphraser": None if args.no_rewrites
        else {"model": PARAPHRASER, "decoding": "beam search, 5 beams, no sampling"},
        "filters": {"chars": [MIN_CHARS, MAX_CHARS], "deepset": "label=1, English by word count",
                    "jayavibhav": f"label=1, random {JAY_SEEDS}"},
        "counts": {"seeds": len(seeds), "controls": len(controls), **counts},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  wrote {len(variants)} variants: {counts}, and {len(controls)} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
