"""Dev-only launcher: start multiple adapters as local subprocesses.

This is a developer convenience that used to live inside the gateway. The
standalone engine no longer spawns adapters; run this alongside the engine to
bring up adapters locally. Production runs each adapter as its own service.
"""

from __future__ import annotations

import subprocess
import sys

from mypalclara.adapters.manifest import list_adapters


def main(argv: list[str] | None = None) -> None:
    names = (argv or sys.argv[1:]) or list_adapters()
    procs: list[subprocess.Popen] = []
    for name in names:
        cmd = [sys.executable, "-m", f"mypalclara.adapters.{name}"]
        print(f"[launch] starting {name}: {' '.join(cmd)}")
        procs.append(subprocess.Popen(cmd))
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
