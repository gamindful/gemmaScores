"""Assemble detected symbols into bars, hands and positions.

The accompaniment figure repeats four times in a bar, so the reading of each
column can be checked against its three repeats. That vote is what makes the
result stable: an isolated mis-read loses to the three columns that agree.
"""

import collections

from . import omr_core as C
from .omr_notes import SystemReader, spell, to_midi, REF


def columns(notes, gap=11):
    """Group noteheads that are struck together (same x) into columns."""
    cols, cur = [], []
    for n in sorted(notes, key=lambda d: d["x"]):
        if cur and n["x"] - cur[-1]["x"] > gap:
            cols.append(cur)
            cur = []
        cur.append(n)
    if cur:
        cols.append(cur)
    return cols


def apply_accidentals(bar_notes):
    """An accidental holds for its letter and octave to the end of the bar."""
    state = {}
    for n in sorted(bar_notes, key=lambda d: d["x"]):
        if n["alter"] is not None:
            state[n["index"]] = n["alter"]
    for n in bar_notes:
        if n["alter"] is None:
            n["alter"] = state.get(n["index"], None)


KEY_SHARPS = {3, 0, 4, 1}  # F#, C#, G#, D# as diatonic letter numbers


def default_alter(index):
    return 1 if index % 7 in KEY_SHARPS else 0


def read_bar(bar_notes):
    """Split one bar into the repeating figure, the melody and the bass."""
    apply_accidentals(bar_notes)
    for n in bar_notes:
        if n["alter"] is None:
            n["alter"] = default_alter(n["index"])
        n["midi"] = to_midi(n["index"], n["alter"])
        n["name"] = spell(n["index"], n["alter"])

    cols = columns(bar_notes)
    if len(cols) < 6:
        # a bar that is one chord, such as the closing fermata: split by staff,
        # then hand the left hand's top notes over if its reach is impossible
        right = [n for n in bar_notes if n["clef"] == "tre"]
        left = sorted((n for n in bar_notes if n["clef"] == "bas"),
                      key=lambda n: n["midi"])
        while len(left) > 1 and left[-1]["midi"] - left[0]["midi"] > 19:
            right.append(left.pop())
        return {"groups": [], "chord": bar_notes, "melody": right,
                "bass": left, "cols": len(cols)}

    # The accompaniment runs in threes. When the count is off by one or two,
    # an end column holding nothing that recurs in the bar is a stray reading.
    counts = collections.Counter(n["midi"] for n in bar_notes)
    while len(cols) % 3 and len(cols) > 6:
        for end in (0, -1):
            if all(counts[n["midi"]] == 1 for n in cols[end]):
                cols.pop(end)
                break
        else:
            break

    # Trim to the 12 accompaniment columns when the engraving gives more.
    n_groups = max(1, round(len(cols) / 3))
    chosen, used = [], set()
    for gi in range(n_groups):
        group = cols[gi * 3:gi * 3 + 3]
        if len(group) < 3:
            break
        picks = []
        for ci, col in enumerate(group):
            cands = [n for n in col if not n["hollow"]] or col
            # a figure note recurs at the same place in the other groups
            def score(n):
                hits = 0
                for gj in range(n_groups):
                    other = cols[gj * 3 + ci] if gj * 3 + ci < len(cols) else []
                    if any(m["midi"] == n["midi"] for m in other):
                        hits += 1
                return (hits, -n["midi"])
            best = max(cands, key=score)
            picks.append(best)
            used.add(id(best))
        chosen.append(picks)

    rest = [n for n in bar_notes if id(n) not in used]
    melody = [n for n in rest if n["clef"] == "tre"]
    bass = [n for n in rest if n["clef"] == "bas"]
    # every column's other candidates, for a second opinion later
    spare = [[sorted({n["name"] for n in col}) for col in cols[g * 3:g * 3 + 3]]
             for g in range(len(chosen))]
    return {"groups": chosen, "melody": melody, "bass": bass,
            "cols": len(cols), "spare": spare}


def read_score(pdf_path, keep_pages=False):
    pages = C.pdf_pages(pdf_path)
    bars = []
    system = 0
    for page_no, a in enumerate(pages):
        for s in C.find_systems(a):
            system += 1
            xs = C.annotate_system(a, s)
            R = SystemReader(a, s)
            heads = R.noteheads()
            R.attach_accidentals(heads)
            crop_y = (max(0, int(s["top"] - 10 * s["st"])),
                      min(a.shape[0], int(s["bot"] + 10 * s["sb"])))
            for j in range(len(xs) - 1):
                x0, x1 = xs[j], xs[j + 1]
                notes = [n for n in heads if x0 + 9 < n["x"] < x1 - 4]
                bars.append({"index": len(bars) + 1,
                             "system": system,
                             "notes": notes,
                             "crop": (page_no, x0, crop_y[0], x1, crop_y[1]),
                             "read": read_bar(notes)})
    return (bars, pages) if keep_pages else bars
