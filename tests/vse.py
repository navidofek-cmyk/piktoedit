"""Spusti vsechny zkousky a vypise souhrn.

Pouziti:

    python tests/vse.py            vsechny zkousky
    python tests/vse.py nuz        jen ty, jejichz nazev obsahuje "nuz"
    python tests/vse.py --rychle   vynecha nahodnou zkousku

Navratovy kod je pocet sad, ktere neprosly.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: Poradi od nejrychlejsich k nejpomalejsim, at se chyby ukazou driv.
SUITES = [
    ("zaklad.py", [], "SVG, sablony, popisek, panely"),
    ("prevod.py", [], "prevod na krivku a uzly"),
    ("mys.py", [], "kresleni a rez pres udalosti mysi"),
    ("guma.py", [], "guma"),
    ("nuz.py", [], "nuz, zakladni pripady"),
    ("nuz_okrajove.py", [], "nuz, okrajove pripady"),
    ("nuz_spoje.py", [], "nuz, spoje typu Y"),
    ("nuz_znovu.py", [], "nuz, rezani jiz orezanych kusu"),
    ("nuz_uhly.py", [], "nuz, uhly a konce tahu"),
    ("nuz_nahodne.py", ["20261005", "200"], "nuz, nahodne kresby"),
]

COUNT = re.compile(r"HOTOVO, problemu: (\d+)")


def main(argv: list[str]) -> int:
    only = [arg for arg in argv if not arg.startswith("--")]
    quick = "--rychle" in argv

    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")

    failed: list[str] = []
    total_problems = 0
    started = time.time()

    for name, args, popis in SUITES:
        if quick and name == "nuz_nahodne.py":
            continue
        if only and not any(part in name for part in only):
            continue

        begin = time.time()
        result = subprocess.run([sys.executable, str(TESTS / name), *args],
                                capture_output=True, text=True, env=environment,
                                cwd=str(TESTS))
        output = result.stdout
        match = COUNT.search(output)
        problems = int(match.group(1)) if match else -1
        total_problems += max(0, problems)
        seconds = time.time() - begin

        if problems == 0 and result.returncode == 0:
            print(f"[OK   ] {name:18} {popis:38} {seconds:5.1f}s")
            continue

        failed.append(name)
        print(f"[CHYBA] {name:18} {popis:38} {seconds:5.1f}s"
              f"  problemu: {problems if problems >= 0 else '?'}")
        for line in output.splitlines():
            if line.startswith("  - ") or "CHYBA" in line:
                print(f"         {line.strip()}")
        if result.returncode != 0 and problems < 0:
            print("         " + (result.stderr.strip().splitlines() or ["(bez vypisu)"])[-1])

    print()
    print(f"sad: {len(SUITES)}, neproslo: {len(failed)}, problemu celkem: "
          f"{total_problems}, cas {time.time() - started:.0f}s")
    return len(failed)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
