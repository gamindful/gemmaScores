"""Core optical reading of the ScoreTail engraving: pages -> systems -> measures."""

import io
import numpy as np
from PIL import Image

DARK = 140


def pdf_pages(pdf_path):
    """Return the scan of each page as a greyscale array, in page order.

    The pages of this PDF share one resource dictionary, so the image actually
    drawn on a page has to come from that page's own content stream: the
    `/Name Do` operators, in order.
    """
    import re
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        by_name = {}
        for im in page.images:
            try:
                by_name[im.name.rsplit(".", 1)[0]] = Image.open(io.BytesIO(im.data))
            except Exception:
                pass
        data = page.get_contents().get_data()
        drawn = [n.decode() for n in re.findall(rb"/([A-Za-z0-9_]+)\s+Do", data)]
        best = None
        for name in drawn:
            img = by_name.get(name)
            if img is None:
                continue
            if best is None or img.width * img.height > best.width * best.height:
                best = img
        if best is None:
            raise RuntimeError("no raster image drawn on a page")
        pages.append(np.array(best.convert("L")))
    return pages


def h_lines(a, x0, x1, frac=0.9):
    """Rows that are mostly ink across [x0,x1) -> staff line rows, merged."""
    seg = a[:, x0:x1] < DARK
    ink = seg.sum(axis=1)
    rows = ink > frac * (x1 - x0)
    groups, start = [], None
    for y, v in enumerate(rows):
        if v and start is None:
            start = y
        elif not v and start is not None:
            groups.append((start + y - 1) / 2.0)
            start = None
    if start is not None:
        groups.append((start + len(rows) - 1) / 2.0)
    return groups


def find_systems(a):
    """Group staff lines into (treble5, bass5) systems.

    Staff lines are found over a narrow left-hand window, which every system
    reaches including the short final one.
    """
    # x-window inside every system: the first one is indented by its brace and
    # the final one is only a few hundred pixels wide.
    lines = h_lines(a, 200, 320, frac=0.95)
    # cluster into staves: 5 lines with near-equal spacing
    staves = []
    cur = [lines[0]] if lines else []
    for y in lines[1:]:
        if cur and y - cur[-1] < 26:
            cur.append(y)
        else:
            staves.append(cur)
            cur = [y]
    if cur:
        staves.append(cur)
    staves = [s for s in staves if len(s) == 5]
    systems = []
    for i in range(0, len(staves) - 1, 2):
        systems.append({"tre": staves[i], "bas": staves[i + 1]})
    for s in systems:
        s["x0"] = 0
        s["st"] = (s["tre"][4] - s["tre"][0]) / 8.0
        s["sb"] = (s["bas"][4] - s["bas"][0]) / 8.0
        s["mid"] = (s["tre"][4] + s["bas"][0]) / 2.0
        s["top"] = s["tre"][0]
        s["bot"] = s["bas"][4]
    return systems


def find_barlines(a, sys):
    """Columns of ink spanning the whole grand staff."""
    y0, y1 = int(sys["top"]), int(sys["bot"])
    col = (a[y0:y1 + 1, :] < DARK).sum(axis=0)
    h = y1 - y0 + 1
    cand = np.where(col > 0.90 * h)[0]
    groups = []
    for x in cand:
        if groups and x - groups[-1][-1] <= 4:
            groups[-1].append(x)
        else:
            groups.append([x])
    xs = [int(np.mean(g)) for g in groups if len(g) >= 2]
    # a final double bar is two lines a few pixels apart: keep one
    merged = []
    for x in xs:
        if merged and x - merged[-1] < 30:
            merged[-1] = x
        else:
            merged.append(x)
    return merged


def run_lengths(mask, axis):
    """For every ink pixel, the length of its run along `axis` (0=vertical)."""
    out = np.zeros(mask.shape, dtype=np.int16)
    if axis == 0:
        acc = np.zeros(mask.shape[1], dtype=np.int16)
        for y in range(mask.shape[0]):
            acc = np.where(mask[y], acc + 1, 0)
            out[y] = acc
        acc = np.zeros(mask.shape[1], dtype=np.int16)
        for y in range(mask.shape[0] - 1, -1, -1):
            acc = np.where(mask[y], acc + 1, 0)
            out[y] += acc - np.where(mask[y], 1, 0)
    else:
        acc = np.zeros(mask.shape[0], dtype=np.int16)
        for x in range(mask.shape[1]):
            acc = np.where(mask[:, x], acc + 1, 0)
            out[:, x] = acc
        acc = np.zeros(mask.shape[0], dtype=np.int16)
        for x in range(mask.shape[1] - 1, -1, -1):
            acc = np.where(mask[:, x], acc + 1, 0)
            out[:, x] += acc - np.where(mask[:, x], 1, 0)
    return out


def annotate_system(a, sysinfo):
    """Record where the system's own left-hand edge is."""
    bars = find_barlines(a, sysinfo)
    sysinfo["x0"] = bars[0] if bars else 0
    return bars
