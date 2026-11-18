"""Symbol layer: noteheads, accidentals, beams, and the pitch they spell."""

import numpy as np
from scipy import ndimage as ndi

from .omr_core import DARK, run_lengths

LETTERS = "CDEFGAB"
# diatonic index of the bottom line of each staff: treble E4, bass G2
REF = {"tre": 30, "bas": 18}
# a notehead's centroid sits a little above its true centre
Y_BIAS = 0.18
ALTER_CHAR = {1: "#", 0: "n", -1: "b", 2: "x"}
ALTER_SEMI = {"#": 1, "n": 0, "b": -1, "x": 2}


def spell(index, alter):
    return LETTERS[index % 7] + ALTER_CHAR[alter] + str(index // 7)


def to_midi(index, alter):
    step = [0, 2, 4, 5, 7, 9, 11][index % 7]
    return (index // 7 + 1) * 12 + step + alter


class SystemReader:
    """Everything read off one system of the engraving."""

    def __init__(self, page, sysinfo):
        self.a = page
        self.s = sysinfo
        self.y0 = max(0, int(sysinfo["top"] - 16 * sysinfo["st"]))
        self.y1 = min(page.shape[0], int(sysinfo["bot"] + 16 * sysinfo["sb"]))
        self.bw = page[self.y0:self.y1] < DARK
        self.vr = run_lengths(self.bw, 0)
        self.hr = run_lengths(self.bw, 1)
        # staff and ledger lines run longer than any notehead is wide
        self.nolines = self.bw & ~((self.vr <= 6) & (self.hr >= 26))
        filled = ndi.binary_fill_holes(
            ndi.binary_closing(self.nolines, np.ones((1, 3))))
        self.filled = filled
        self.beams = self.bw & (self.vr >= 7) & (self.hr >= 24)
        self.beam_lab, self.n_beams = ndi.label(self.beams)
        # Clef, key signature and time signature stand before the first note.
        # The first beam marks where the music starts; back off one note width.
        xs = np.where(self.beams.any(axis=0))[0]
        first_beam = int(xs.min()) - 34 if xs.size else 0
        self.music_x = max(sysinfo["x0"] + 115, first_beam)
        # components of the ink with staff lines gone, to tell a notehead's
        # ring (short) from an accidental's counter (tall)
        self.ink_lab, _ = ndi.label(self.nolines)
        self.ink_box = ndi.find_objects(self.ink_lab)

    # ------------------------------------------------------------ geometry

    def step_index(self, y):
        clef = "tre" if y < self.s["mid"] else "bas"
        ref_y = self.s["tre"][4] if clef == "tre" else self.s["bas"][4]
        step = self.s["st"] if clef == "tre" else self.s["sb"]
        k = (ref_y - (y + Y_BIAS * step)) / step
        return clef, REF[clef] + int(round(k)), abs(k - round(k))

    @staticmethod
    def _blobs(mask):
        lab, _ = ndi.label(mask)
        for i, sl in enumerate(ndi.find_objects(lab), start=1):
            if sl is not None:
                yield sl, lab[sl] == i

    # ------------------------------------------------------------ symbols

    def ring_is_notehead(self, sl):
        """A hole counts only if the ink beside it is a notehead's ring.

        A sharp or natural encloses a counter of much the same size, but it is
        bounded by strokes twice as tall as a notehead. A stem may lengthen one
        side of a real head, never both, so the shorter side decides.
        """
        y = (sl[0].start + sl[0].stop) // 2
        if not (0 <= y < self.vr.shape[0]):
            return False
        runs = []
        for x in (sl[1].start - 2, sl[1].stop + 1):
            if not (0 <= x < self.vr.shape[1]):
                return False
            col = self.vr[max(0, y - 3):y + 4, x]
            runs.append(int(col.max()) if col.size else 0)
        return 4 <= min(runs) <= 26

    def ledger_ok(self, x, clef, off):
        """Outside the five lines, a real notehead rides on a ledger line."""
        if -1 <= off <= 9:
            return True
        line = off if off % 2 == 0 else (off - 1 if off > 9 else off + 1)
        step = self.s["st"] if clef == "tre" else self.s["sb"]
        ref_y = self.s["tre"][4] if clef == "tre" else self.s["bas"][4]
        y = int(round(ref_y - line * step)) - self.y0
        if not (1 <= y < self.bw.shape[0] - 1):
            return False
        band = self.bw[y - 1:y + 2, max(0, int(x) - 11):int(x) + 12]
        return band.any(axis=0).mean() > 0.7

    def noteheads(self):
        cands = []
        # filled heads: a solid core survives erosion in both directions
        core = self.bw & (self.vr >= 9) & (self.hr >= 12)
        for sl, blob in self._blobs(core):
            h, w = blob.shape
            if not (8 <= h <= 18 and 11 <= w <= 26 and 1.0 <= w / h <= 2.3):
                continue
            if blob.sum() < 70:
                continue
            ys, xs = np.where(blob)
            cands.append({"x": xs.mean() + sl[1].start,
                          "y": ys.mean() + sl[0].start + self.y0,
                          "hollow": False})
        # hollow heads, second reading: fill the ring in and look for the same
        # solid core as a filled head. Catches rings the hole pass misses.
        vrf = run_lengths(self.filled, 0)
        hrf = run_lengths(self.filled, 1)
        for sl, blob in self._blobs(self.filled & (vrf >= 9) & (hrf >= 12)):
            h, w = blob.shape
            if not (8 <= h <= 18 and 11 <= w <= 26 and 1.0 <= w / h <= 2.3):
                continue
            if blob.sum() < 70:
                continue
            ys, xs = np.where(blob)
            cands.append({"x": xs.mean() + sl[1].start,
                          "y": ys.mean() + sl[0].start + self.y0,
                          "hollow": True})
        # hollow heads: found by the hole inside the ring. The hole is read off
        # the untouched image, because a staff line crossing the head cuts the
        # ring open once the lines are taken out; it only splits the hole in two.
        raw = ndi.binary_fill_holes(self.bw) & ~self.bw
        pieces = []
        for sl, blob in self._blobs(raw):
            h, w = blob.shape
            if not (2 <= h <= 16 and 4 <= w <= 18 and blob.sum() >= 12):
                continue
            pieces.append([sl[0].start, sl[0].stop, sl[1].start, sl[1].stop,
                           float(blob.sum())])
        pieces.sort(key=lambda p: (p[2], p[0]))
        merged = []
        for p in pieces:
            for q in merged:
                overlap = min(p[3], q[3]) - max(p[2], q[2])
                if overlap > 0.6 * min(p[3] - p[2], q[3] - q[2]) and \
                        max(p[0], q[0]) - min(p[1], q[1]) <= 7:
                    q[0], q[1] = min(p[0], q[0]), max(p[1], q[1])
                    q[2], q[3] = min(p[2], q[2]), max(p[3], q[3])
                    q[4] += p[4]
                    break
            else:
                merged.append(list(p))
        for y0, y1, x0, x1, area in merged:
            h, w = y1 - y0, x1 - x0
            if not (7 <= h <= 17 and 7 <= w <= 18 and area >= 45):
                continue
            sl = (slice(y0, y1), slice(x0, x1))
            if not self.ring_is_notehead(sl):
                continue
            cands.append({"x": (x0 + x1 - 1) / 2.0,
                          "y": (y0 + y1 - 1) / 2.0 + self.y0,
                          "hollow": True})

        cands.sort(key=lambda d: (d["x"], d["y"]))
        heads = []
        for d in cands:
            if d["x"] < self.music_x:
                continue
            if any(abs(d["x"] - k["x"]) < 10 and abs(d["y"] - k["y"]) < 9 for k in heads):
                continue
            clef, idx, err = self.step_index(d["y"])
            off = idx - REF[clef]
            if err > 0.30 or not (-13 <= off <= 15):
                continue
            if not self.ledger_ok(d["x"], clef, off):
                continue
            d.update(clef=clef, index=idx, err=err, off=off, alter=None, beam=None)
            heads.append(d)
        for d in heads:
            d["beam"] = self.beam_of(d)
        return heads

    def beam_of(self, note):
        """Label of the beam this note's stem reaches, or None."""
        if note["hollow"]:
            return None
        cx = int(note["x"])
        cy = int(note["y"]) - self.y0
        band = self.beam_lab[max(0, cy - 80):cy + 80, max(0, cx - 11):cx + 12]
        vals = band[band > 0]
        if vals.size == 0:
            return None
        return int(np.bincount(vals).argmax())

    # -------------------------------------------------------- accidentals

    def attach_accidentals(self, heads):
        """Find accidental glyphs and bind each to the notehead it governs."""
        step = self.s["st"]
        for sl, blob, dy in self._accidental_blobs():
            h, w = blob.shape
            x0, x1 = sl[1].start, sl[1].stop
            ys, xs = np.where(blob)
            gx, gy = xs.mean() + x0, ys.mean() + sl[0].start + dy + self.y0
            top = sl[0].start + dy + self.y0
            if any(x0 <= n["x"] <= x1 and top <= n["y"] <= top + h for n in heads):
                continue
            kind = self.classify(blob, h, w)
            if kind is None:
                continue
            best, bestdx = None, 1e9
            for n in heads:
                dx = n["x"] - x1
                if not (-2 <= dx <= 30):
                    continue
                if abs(n["y"] - gy) > 0.75 * step:
                    continue
                if dx < bestdx:
                    best, bestdx = n, dx
            if best is not None and best["alter"] is None:
                best["alter"] = ALTER_SEMI[kind]

    def _accidental_blobs(self):
        """Candidate glyphs, splitting a stack of accidentals that touch."""
        for sl, blob in self._blobs(self.nolines):
            h, w = blob.shape
            if not (7 <= w <= 21 and blob.sum() >= 40):
                continue
            if 9 <= h <= 46:
                yield sl, blob, 0
            elif h <= 140:
                n = int(round(h / 42.0))
                if n < 2:
                    continue
                cut = h / n
                for k in range(n):
                    a, b = int(k * cut), int((k + 1) * cut)
                    part = blob[a:b]
                    if part.sum() >= 40:
                        yield (slice(sl[0].start, sl[0].start + (b - a)), sl[1]), part, a

    @staticmethod
    def classify(blob, h, w):
        """This engraving draws a natural narrower than a sharp: 10px vs 12-13."""
        if h <= 19:
            if 0.75 <= w / h <= 1.4 and blob.sum() >= 90:
                return "x"
            return None
        if h < 24:
            return None
        if h >= 36:
            return "n" if w <= 11 else "#"
        half = max(1, w // 2)

        def extent(part):
            rows = np.where(part.any(axis=1))[0]
            return (rows[0] / h, rows[-1] / h) if len(rows) else (1.0, 0.0)

        topL, botL = extent(blob[:, :half])
        topR, botR = extent(blob[:, half:])
        if botL < 0.90 and topR > 0.08:
            return "n"
        if botL >= 0.90 and topR > 0.30:
            return "b"
        return "#"
