"""Second opinion from a local model on the bars the detector is unsure about.

The model is never asked to read music from scratch, which a small model does
badly. It is asked to choose between readings the detector actually measured:
the accompaniment figure is played four times a bar, so when those four
readings disagree one of them is a mis-read, and picking the right one is a
judgement a language model can make from the harmony around it.
"""

from PIL import Image

from .llm import Ollama, Unavailable, first_json

SYSTEM = (
    "You check a computer's reading of a piano score. You never invent notes: "
    "you only choose between readings you are given. Answer with JSON only."
)

TEMPLATE = """Bar {bar} of Beethoven's Moonlight Sonata, first movement (C# minor).

The right hand plays a three-note broken chord, once per beat, four times in
this bar. A note reader read each of the four beats separately and got:

{beats}

Beats {majority_beats} agree on "{majority}". Beat(s) {odd_beats} came out
different. Either the odd one out is a mis-reading of the same chord, or the
harmony really does change inside the bar.

The left hand under them reads: {bass}
The bar before was read as: {before}
The bar after was read as: {after}
{image_note}
Answer "same" if the whole bar is one chord and the odd beat is a mis-reading,
or "changes" if the harmony genuinely changes part-way through the bar.

Reply with JSON like {{"verdict": "same", "why": "..."}} - "why" at most
fifteen words."""


def letters(n):
    return [chr(ord("A") + i) for i in range(n)]


def bar_options(read):
    """Distinct readings of the figure in this bar, in order of first use."""
    seen, opts = [], []
    for group in read["groups"]:
        names = tuple(n["name"] for n in sorted(group, key=lambda d: d["midi"]))
        if names not in seen:
            seen.append(names)
            opts.append(names)
    return opts


def describe(read):
    if read is None or not read.get("groups"):
        return "-"
    opts = bar_options(read)
    return " / ".join(" ".join(o) for o in opts)


def crop(pages, bar, pad=14):
    page_no, x0, y0, x1, y1 = bar["crop"]
    a = pages[page_no]
    box = (max(0, x0 - pad), y0, min(a.shape[1], x1 + pad), y1)
    im = Image.fromarray(a[box[1]:box[3], box[0]:box[2]])
    # a small model sees a wide thin strip badly; give it a readable height
    scale = min(3.0, 900.0 / max(1, im.width))
    if scale > 1.05:
        im = im.resize((int(im.width * scale), int(im.height * scale)),
                       Image.LANCZOS)
    return im.convert("L")


def names_of(group):
    return tuple(n["name"] for n in sorted(group, key=lambda d: d["midi"]))


def split_bar(read):
    """The reading most beats agree on, and the beats that differ from it.

    Returns None when there is nothing to arbitrate: either every beat agrees,
    or no reading is backed by more than one beat, in which case there is no
    corroborated chord to snap the odd beat to and the model is not asked.
    """
    groups = read.get("groups") or []
    if len(groups) < 3:
        return None
    tally = {}
    for g in groups:
        tally.setdefault(names_of(g), []).append(g)
    if len(tally) < 2:
        return None
    best = max(tally.values(), key=len)
    if len(best) < 2 or len(best) == len(groups):
        return None
    majority = names_of(best[0])
    odd = [i for i, g in enumerate(groups) if names_of(g) != majority]
    return majority, best[0], odd


def review_bars(bars, pages, client, use_images=True, limit=None,
                progress=None):
    """Settle the bars where one beat disagrees with the rest.

    The model never picks notes. It answers one question: is the odd beat a
    mis-reading of the chord the other beats agree on, or a real change of
    harmony inside the bar? Only a "same" answer changes anything, and only
    towards a reading the detector already made twice.
    """
    stats = {"asked": 0, "changed": 0, "same": 0, "changes": 0, "unusable": 0}
    for i, bar in enumerate(bars):
        read = bar["read"]
        if read is None:
            continue
        split = split_bar(read)
        if split is None:
            continue
        if limit is not None and stats["asked"] >= limit:
            break
        majority, model_group, odd = split
        stats["asked"] += 1

        groups = read["groups"]
        beats = "\n".join(
            f"  beat {k + 1}: {' '.join(names_of(g))}"
            for k, g in enumerate(groups))
        images = [crop(pages, bar)] if use_images else []
        prompt = TEMPLATE.format(
            bar=bar["index"],
            beats=beats,
            majority=" ".join(majority),
            majority_beats=", ".join(str(k + 1) for k in range(len(groups))
                                     if k not in odd),
            odd_beats=", ".join(str(k + 1) for k in odd),
            bass=" ".join(sorted({n["name"] for n in read["bass"]})) or "-",
            before=describe(bars[i - 1]["read"]) if i else "-",
            after=describe(bars[i + 1]["read"]) if i + 1 < len(bars) else "-",
            image_note=("\nThe picture of this bar is attached.\n"
                        if images else ""))
        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["same", "changes"]},
                "why": {"type": "string"},
            },
            "required": ["verdict"],
        }
        try:
            content, _ = client.ask(prompt, images=images, system=SYSTEM,
                                    schema=schema)
        except Unavailable:
            raise
        answer = first_json(content) or {}
        verdict = str(answer.get("verdict", "")).strip().lower()
        why = str(answer.get("why", ""))[:70]

        if verdict == "same":
            snap(read, model_group, odd)
            stats["same"] += 1
            stats["changed"] += len(odd)
            outcome = "snapped beat(s) " + ",".join(str(k + 1) for k in odd)
        elif verdict == "changes":
            read["reviewed"] = True
            stats["changes"] += 1
            outcome = "left as read"
        else:
            stats["unusable"] += 1
            outcome = "no usable answer"
        if progress:
            progress(bar["index"], " ".join(majority), outcome, why)
    return stats


def snap(read, model_group, odd):
    """Give the odd beats the pitches of the corroborated reading."""
    template = sorted(model_group, key=lambda d: d["midi"])
    for k in odd:
        group = sorted(read["groups"][k], key=lambda d: d["midi"])
        rebuilt = []
        for note, model in zip(group, template):
            copy = dict(note)
            for field in ("index", "alter", "midi", "name", "clef", "off"):
                if field in model:
                    copy[field] = model[field]
            rebuilt.append(copy)
        if len(rebuilt) == len(template):
            read["groups"][k] = rebuilt
    read["reviewed"] = True


def make_client(model, host, think):
    return Ollama(model=model, host=host, think=think)
