#!/usr/bin/env python3
"""Read the hand positions, with fingering, out of a scanned piano score.

The only input is the PDF. Nothing about the music is hard-coded: the program
finds the staves, the barlines, the noteheads and the accidentals in the page
images, works out the pitch each notehead spells, splits the texture into the
accompaniment figure, the melody and the bass, and fingers each position.

    python3 read_hand_positions.py "Moonlight Sonata 1st Mov.pdf"
    python3 read_hand_positions.py score.pdf --json positions.json
    python3 read_hand_positions.py score.pdf --selftest

Written for the ScoreTail engraving of Beethoven's Op. 27 No. 2; the staff
geometry is measured from the page, so other scans of the same size and style
should read too.

Needs: pypdf, pillow, numpy, scipy.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moonlight_omr import llm, page, review, selftest
from moonlight_omr.positions import extract


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", help="the scanned score")
    ap.add_argument("--html", default="Moonlight Hand Positions.html",
                    help="page to write (default: %(default)s)")
    ap.add_argument("--json", help="also write the positions as JSON")
    ap.add_argument("--selftest", action="store_true",
                    help="compare with the hand-verified bars and stop")
    ap.add_argument("--think", nargs="?", const="true", default="false",
                    metavar="true|false",
                    help="have a local model settle the bars whose four "
                         "readings disagree (needs Ollama running)")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL,
                    help="local model to ask (default: %(default)s)")
    ap.add_argument("--host", default=llm.DEFAULT_HOST,
                    help="Ollama address (default: %(default)s)")
    ap.add_argument("--no-images", action="store_true",
                    help="ask without sending the picture of the bar")
    ap.add_argument("--limit", type=int,
                    help="stop after this many bars have been asked about")
    args = ap.parse_args()

    think = str(args.think).strip().lower() in ("1", "true", "yes", "on")
    reviewer = None
    client = None
    if think:
        try:
            client = review.make_client(args.model, args.host, think=True)
        except llm.Unavailable as exc:
            print(f"--think: {exc}", file=sys.stderr)
            return 2
        print(f"--think: asking {client.model} at {args.host}"
              f"{'' if args.no_images else ', with the bar images'}")

        def reviewer(bars, pages):
            stats = review.review_bars(
                bars, pages, client,
                use_images=not args.no_images, limit=args.limit,
                progress=lambda bar, chord, outcome, why: print(
                    f"  bar {bar:2d}: {chord:<16} {outcome}"
                    + (f"  ({why})" if why else "")))
            print(f"--think: {stats['asked']} bars arbitrated, "
                  f"{stats['same']} one chord, {stats['changes']} real change, "
                  f"{stats['unusable']} no answer; "
                  f"{stats['changed']} beats corrected in "
                  f"{client.seconds:.0f}s")

    positions, n_bars = extract(args.pdf, reviewer=reviewer)
    rows = selftest.run(positions)
    summary = selftest.summary(rows)

    if args.selftest:
        for bar, ok_hands, ok_fig, detail in rows:
            flag = "ok  " if (ok_hands and ok_fig) else "diff"
            print(f"bar {bar:2d} {flag} {detail}")
        print(f"\n{summary['both']}/{summary['bars']} positions fully match, "
              f"{summary['figure']} figures, {summary['hands']} left-hand chords")
        return 0 if summary["both"] == summary["bars"] else 1

    firm = sum(1 for p in positions if p["quality"] == "firm")
    html = page.render(positions, {"bars": n_bars}, rows, summary)
    with open(args.html, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{args.html}: {len(positions)} positions over {n_bars} bars "
          f"({firm} corroborated, {len(positions) - firm} unconfirmed)")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(positions, fh, indent=1)
        print(f"{args.json}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
