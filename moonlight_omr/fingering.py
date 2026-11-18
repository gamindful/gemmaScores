"""Fingering chosen from the shape of the position, not from the bar that follows.

Right hand: the thumb takes the lowest note of the figure; the outer finger is
held back to 4 when a melody note sits above the figure, so 5 stays free for it.
Left hand: 5 on the bottom, 1 on top, the inner notes filled in between.
"""


def rh_figure(pitches, cap=5):
    """pitches ascending, in MIDI numbers -> one finger each."""
    if not pitches:
        return []
    if len(pitches) == 1:
        return [1]
    span = pitches[-1] - pitches[0]
    if span > 12:
        # wider than the hand: the thumb plays twice and the hand shifts
        fingers = [1]
        for a, b in zip(pitches, pitches[1:]):
            fingers.append(1 if b - a > 12 else min(cap, fingers[-1] + 2))
        return fingers
    if len(pitches) == 3:
        d1 = pitches[1] - pitches[0]
        second = 2 if d1 <= 5 else 3
        if span <= 4:
            third = second + 1
        elif span <= 7:
            third = second + 1 if cap == 4 else second + 2
        else:
            third = cap
        return [1, second, max(second + 1, min(cap, third))]
    # any other size: step a finger per interval, never past the cap
    fingers = [1]
    for a, b in zip(pitches, pitches[1:]):
        gap = b - a
        step = 1 if gap <= 4 else (2 if gap <= 7 else 3)
        fingers.append(min(cap, fingers[-1] + step))
    for i in range(1, len(fingers)):
        if fingers[i] <= fingers[i - 1]:
            fingers[i] = min(cap, fingers[i - 1] + 1)
    return fingers


def lh_chord(pitches):
    """pitches ascending -> fingers, 5 at the bottom and 1 on top."""
    n = len(pitches)
    if n == 0:
        return []
    if n == 1:
        return [5]
    table = {2: [5, 1], 3: [5, 2, 1], 4: [5, 3, 2, 1], 5: [5, 4, 3, 2, 1]}
    if n in table:
        return table[n]
    return [5] + [4] * (n - 2) + [1]


def assign(lh_pitches, rh_pitches, melody_pitch=None):
    """Finger a whole position. Returns (lh fingers, rh fingers, melody finger)."""
    lh = lh_chord(sorted(lh_pitches))
    above = melody_pitch is not None and rh_pitches and melody_pitch > max(rh_pitches)
    rh = rh_figure(sorted(rh_pitches), cap=4 if above else 5)
    mel = None
    if melody_pitch is not None:
        if above:
            mel = 5
        elif rh_pitches and melody_pitch in rh_pitches:
            mel = rh[sorted(rh_pitches).index(melody_pitch)]
        else:
            mel = 5 if not rh_pitches else max(1, min(5, rh[-1]))
    return lh, rh, mel
