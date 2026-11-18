"""Turn the read bars into the sequence of hand positions through the score."""

import collections

from . import fingering
from .omr_score import columns, read_score


def bass_events(bass_notes):
    """Bass notes struck together, in order through the bar."""
    return columns(bass_notes, gap=14)


def bar_positions(bar, carried):
    """One entry per accompaniment group, plus whatever the left hand holds."""
    read = bar["read"]
    out = []
    if read is None:
        return out, carried

    events = bass_events(read["bass"])

    if not read["groups"]:                       # a single chord, e.g. the end
        lh = sorted(n["midi"] for n in read["bass"])
        rh = sorted(n["midi"] for n in read["melody"])
        names = {n["midi"]: n["name"] for n in bar["notes"]}
        out.append(make(bar["index"], 1, lh, rh, None, names, "chord"))
        return out, (lh, names)

    for gi, group in enumerate(read["groups"]):
        x_end = max(n["x"] for n in group)
        struck = [e for e in events if min(n["x"] for n in e) <= x_end + 6]
        if struck:
            lh_notes = struck[-1]
            carried = (sorted(n["midi"] for n in lh_notes),
                       {n["midi"]: n["name"] for n in lh_notes})
        lh, lh_names = carried if carried else ([], {})

        x_lo = min(n["x"] for n in group) - 6
        mel = [n for n in read["melody"] if x_lo <= n["x"] <= x_end + 6]
        mel_note = max(mel, key=lambda n: n["midi"]) if mel else None

        rh = sorted(n["midi"] for n in group)
        names = dict(lh_names)
        names.update({n["midi"]: n["name"] for n in group})
        if mel_note:
            names[mel_note["midi"]] = mel_note["name"]

        # the figure comes round four times a bar: a reading another group
        # agrees with is firm, one that stands alone is worth checking
        same = sum(1 for g in read["groups"]
                   if sorted(n["midi"] for n in g) == rh)
        quality = "firm" if same >= 2 else "check"
        if read.get("reviewed") and quality == "check":
            quality = "reviewed"
        out.append(make(bar["index"], gi + 1, lh, rh,
                        mel_note["midi"] if mel_note else None, names, quality))
    return out, carried


def make(bar, beat, lh, rh, mel, names, quality):
    lf, rf, mf = fingering.assign(lh, rh, mel)
    def tag(ms, fs):
        return [[names.get(m, str(m)), f] for m, f in zip(sorted(ms), fs)]
    return {
        "bar": bar, "beat": beat, "quality": quality,
        "lh": tag(lh, lf),
        "rh": tag(rh, rf),
        "mel": [names.get(mel, str(mel)), mf] if mel is not None else None,
    }


def key(pos):
    return (tuple(n for n, _ in pos["lh"]),
            tuple(n for n, _ in pos["rh"]),
            pos["mel"][0] if pos["mel"] else None)


def extract(pdf_path, reviewer=None):
    """Every hand position in the score, with repeats of the same shape merged.

    `reviewer`, when given, is called with (bars, pages) after the optical read
    and may correct bars in place before the positions are built.
    """
    bars, pages = read_score(pdf_path, keep_pages=True)
    if reviewer is not None:
        reviewer(bars, pages)
    raw, carried = [], None
    for bar in bars:
        got, carried = bar_positions(bar, carried)
        for g in got:
            g["system"] = bar["system"]
        raw.extend(got)

    merged = []
    for pos in raw:
        if merged and key(merged[-1]) == key(pos):
            merged[-1]["until"] = pos["bar"]
            if pos["quality"] == "firm":
                merged[-1]["quality"] = "firm"
            continue
        pos["until"] = pos["bar"]
        merged.append(pos)
    return merged, len(bars)
