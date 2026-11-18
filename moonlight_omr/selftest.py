"""Regression test: twenty-two positions read off the engraving by eye.

These are the first beat of each system, checked note by note against a pitch
grid laid over the scan. They are the yardstick for the automatic reading, not
an input to it -- nothing here is ever written into the output.
"""

VERIFIED = {
    1:  (["C#2", "C#3"],          ["G#3", "C#4", "E4"]),
    4:  (["G#1", "G#2"],          ["G#3", "B#3", "F#4"]),
    8:  (["B1", "B2"],            ["G#3", "B3", "E4"]),
    12: (["Cn2", "Cn3"],          ["Gn3", "Cn4", "E4"]),
    15: (["B1", "B2"],            ["B3", "Dn4", "F#4"]),
    18: (["B1", "B2"],            ["B3", "E4", "Gn4"]),
    21: (["B1", "B2"],            ["Gn3", "B3", "Dn4"]),
    24: (["E#2", "C#3", "E#3"],   ["C#4", "G#4", "B4"]),
    27: (["C#2", "G#2", "C#3"],   ["E4", "G#4", "C#5"]),
    30: (["G#1", "G#2"],          ["E3", "E4", "G#4"]),
    33: (["G#1", "G#2"],          ["E3", "G#3", "C#4"]),
    36: (["G#1", "G#2"],          ["F#5", "A5", "B#5"]),
    39: (["G#1", "G#2"],          ["B#2", "F#3", "G#3"]),
    42: (["C#2", "G#2", "C#3"],   ["E3", "G#3", "C#4"]),
    46: (["E2", "E3"],            ["G#3", "B3", "E4"]),
    49: (["B#1", "G#2", "B#2"],   ["D#4", "F#4", "G#4"]),
    52: (["C#2", "C#3"],          ["C#4", "F#4", "A4"]),
    55: (["C#2", "C#3"],          ["C#4", "E#4", "G#4"]),
    58: (["A1", "A2"],            ["F#3", "C#4", "D#4"]),
    62: (["C#2", "G#2"],          ["G#3", "C#4", "E4"]),
    65: (["G#1", "G#2"],          ["A4", "B#4", "D#5"]),
    69: (["C#2", "G#2", "C#3"],   ["E3", "G#3", "C#4"]),
}

STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    letter, rest = name[0], name[1:]
    alter = 0
    if rest and rest[0] in "#bnx":
        alter = {"#": 1, "b": -1, "n": 0, "x": 2}[rest[0]]
        rest = rest[1:]
    return (int(rest) + 1) * 12 + STEP[letter] + alter


def run(positions):
    """Compare the first position of each listed bar with the verified reading."""
    first = {}
    for p in positions:
        first.setdefault(p["bar"], p)
    rows = []
    for bar, (lh, rh) in sorted(VERIFIED.items()):
        got = first.get(bar)
        if got is None:
            rows.append((bar, False, False, "no reading"))
            continue
        got_lh = sorted(midi(n) for n, _ in got["lh"])
        got_rh = sorted(midi(n) for n, _ in got["rh"])
        ok_lh = set(got_lh) >= set(midi(n) for n in lh)
        ok_rh = got_rh == sorted(midi(n) for n in rh)
        detail = "" if (ok_lh and ok_rh) else \
            "read %s / %s" % ([n for n, _ in got["lh"]], [n for n, _ in got["rh"]])
        rows.append((bar, ok_lh, ok_rh, detail))
    return rows


def summary(rows):
    both = sum(1 for _, a, b, _ in rows if a and b)
    return {"bars": len(rows), "both": both,
            "hands": sum(1 for _, a, _, _ in rows if a),
            "figure": sum(1 for _, _, b, _ in rows if b)}
