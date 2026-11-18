#!/usr/bin/env python3
"""Render Beethoven's Moonlight Sonata, 1st movement, as a playable MIDI file.

Source data
-----------
The note data below is everything that was measured off "Moonlight Sonata 1st
Mov.pdf": the first simultaneity of each of the 22 grand staves (bars 1, 4, 8,
12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 46, 49, 52, 55, 58, 62, 65, 69) --
the left-hand bass notes, the right-hand triplet group, and the melody note
where one is struck on the downbeat.

What this produces
------------------
All 69 bars, in the movement's real proportions: each measured harmony is held
from its own bar until the next measured bar, with the triplet figure running
continuously underneath in the written Adagio sostenuto texture, the bass
restruck each bar, and the melody note sounding on each downbeat.

It is therefore a faithful *outline*, not a note-for-note transcription: the
harmony is correct wherever the score was sampled, and the inner voice motion
and the melody's dotted rhythms between those points are not represented.

Usage:  python3 moonlight_outline.py [output.mid]
"""

import struct
import sys

# ---------------------------------------------------------------- score data

# bar, left hand, right-hand triplet group, melody note on the downbeat
POSITIONS = [
    (1,  ["C#2", "C#3"],              ["G#3", "C#4", "E4"],   None),
    (4,  ["G#1", "G#2"],              ["G#3", "B#3", "F#4"],  None),
    (8,  ["B1", "B2"],                ["G#3", "B3", "E4"],    "G#4"),
    (12, ["Cn2", "Cn3"],              ["Gn3", "Cn4", "E4"],   "Gn4"),
    (15, ["B1", "B2"],                ["B3", "Dn4", "F#4"],   None),
    (18, ["B1", "B2"],                ["B3", "E4", "Gn4"],    "Cn5"),
    (21, ["B1", "B2"],                ["Gn3", "B3", "Dn4"],   "Gn4"),
    (24, ["E#2", "C#3", "E#3"],       ["C#4", "G#4", "B4"],   "C#5"),
    (27, ["C#2", "G#2", "C#3"],       ["E4", "G#4", "C#5"],   "E5"),
    (30, ["G#1", "G#2"],              ["E3", "E4", "G#4"],    None),
    (33, ["G#1", "G#2"],              ["E3", "G#3", "C#4"],   None),
    (36, ["G#1", "G#2"],              ["F#5", "A5", "B#5"],   None),
    (39, ["G#1", "G#2"],              ["B#2", "F#3", "G#3"],  None),
    (42, ["C#2", "G#2", "C#3"],       ["E3", "G#3", "C#4"],   None),
    (46, ["E2", "E3"],                ["G#3", "B3", "E4"],    "E4"),
    (49, ["B#1", "G#2", "B#2"],       ["D#4", "F#4", "G#4"],  "D#5"),
    (52, ["C#2", "C#3"],              ["C#4", "F#4", "A4"],   "Dn5"),
    (55, ["C#2", "C#3"],              ["C#4", "E#4", "G#4"],  "C#5"),
    (58, ["A1", "A2"],                ["F#3", "C#4", "D#4"],  "F#4"),
    (62, ["C#2", "G#2"],              ["G#3", "C#4", "E4"],   None),
    (65, ["G#1", "G#2"],              ["A4", "B#4", "D#5"],   None),
    (69, ["C#2", "G#2", "C#3"],       ["E3", "G#3", "C#4"],   None),   # final chord
]

LAST_BAR = 69

# ------------------------------------------------------------------- timing

PPQ = 480                  # ticks per quarter note
BAR = 4 * PPQ              # alla breve: one bar = four quarters
TRIPLET = PPQ // 3         # one triplet eighth = a third of a quarter
QUARTER_BPM = 54           # Adagio sostenuto

V_TRIPLET = 42             # sempre pianissimo
V_BASS = 50
V_MELODY = 66

# ------------------------------------------------------------- pitch parsing

STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    """'C#2' -> 37, 'Gn4' -> 67 ('n' marks a written natural)."""
    letter, rest = name[0], name[1:]
    alter = 0
    if rest and rest[0] in "#bn":
        alter = {"#": 1, "b": -1, "n": 0}[rest[0]]
        rest = rest[1:]
    return (int(rest) + 1) * 12 + STEP[letter] + alter


# --------------------------------------------------------------- MIDI output


def vlq(n):
    """Variable-length quantity, as MIDI delta times are encoded."""
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def chunk(tag, body):
    return tag + struct.pack(">I", len(body)) + body


def track(events, name):
    """events: list of (tick, status_byte, data1, data2), already unsorted."""
    body = bytearray()
    body += vlq(0) + b"\xff\x03" + bytes([len(name)]) + name.encode()
    # note-offs before note-ons at the same tick, so repeated pitches re-attack
    events = sorted(events, key=lambda e: (e[0], e[1] & 0xF0 != 0x80))
    prev = 0
    for tick, status, d1, d2 in events:
        body += vlq(tick - prev) + bytes([status, d1, d2])
        prev = tick
    body += vlq(0) + b"\xff\x2f\x00"
    return chunk(b"MTrk", bytes(body))


def conductor():
    body = bytearray()
    body += vlq(0) + b"\xff\x03" + bytes([len("Adagio sostenuto")]) + b"Adagio sostenuto"
    usec = 60_000_000 // QUARTER_BPM
    body += vlq(0) + b"\xff\x51\x03" + usec.to_bytes(3, "big")
    body += vlq(0) + b"\xff\x58\x04" + bytes([2, 1, 24, 8])       # 2/2
    body += vlq(0) + b"\xff\x59\x02" + bytes([4, 1])              # four sharps, minor
    body += vlq(0) + b"\xff\x2f\x00"
    return chunk(b"MTrk", bytes(body))


# ------------------------------------------------------------------- render


def build():
    right, left = [], []

    def note(dest, tick, pitch, dur, vel, ch):
        dest.append((tick, 0x90 | ch, pitch, vel))
        dest.append((tick + dur, 0x80 | ch, pitch, 0))

    def pedal(tick, down, ch):
        right.append((tick, 0xB0 | ch, 64, 127 if down else 0))

    spans = []
    for i, (bar, lh, rh, mel) in enumerate(POSITIONS):
        end = POSITIONS[i + 1][0] if i + 1 < len(POSITIONS) else LAST_BAR + 1
        spans.append((bar, end, lh, rh, mel))

    for start, end, lh, rh, mel in spans:
        t0 = (start - 1) * BAR
        final = start == LAST_BAR

        # "senza sordini": the damper is lifted, and cleared at each new harmony
        pedal(t0, False, 0)
        pedal(t0 + 4, True, 0)

        if final:
            # the closing chord under its fermata, both hands, no triplets
            for n in lh:
                note(left, t0, midi(n), BAR * 2, V_BASS, 1)
            for n in rh:
                note(right, t0, midi(n), BAR * 2, V_BASS + 6, 0)
            right.append((t0 + BAR * 2 + 240, 0xB0, 64, 0))
            continue

        figure = sorted(midi(n) for n in rh)
        for bar in range(start, end):
            tb = (bar - 1) * BAR

            for n in lh:                      # bass, restruck each bar
                note(left, tb, midi(n), BAR, V_BASS, 1)

            for slot in range(12):            # four triplet groups to the bar
                t = tb + slot * TRIPLET
                note(right, t, figure[slot % 3], TRIPLET, V_TRIPLET, 0)

            if mel:                           # melody note on the downbeat
                note(right, tb, midi(mel), BAR - TRIPLET, V_MELODY, 0)

    header = chunk(b"MThd", struct.pack(">HHH", 1, 3, PPQ))
    return header + conductor() + track(right, "Right hand") + track(left, "Left hand")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "Moonlight_1st_Mov_outline.mid"
    data = build()
    with open(out, "wb") as fh:
        fh.write(data)
    beats = LAST_BAR * 4
    print(f"{out}: {len(data)} bytes, {LAST_BAR} bars, "
          f"about {beats * 60 / QUARTER_BPM / 60:.1f} minutes at {QUARTER_BPM} bpm")


if __name__ == "__main__":
    main()
