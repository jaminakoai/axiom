#!/usr/bin/env python3
"""Measure axiom-scan full-file wall time and peak RSS on Linux.

This is a non-gating benchmark. It builds the scanner, creates sparse regular
files of the requested sizes, scans them with a no-match rule, and samples the
child's Linux VmHWM. Sparse files make input generation fast; the scanner still
reads and hashes every logical byte. Results are not a substitute for measuring
representative user files or other platforms.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]


def peak_rss_kib(pid: int) -> int:
    status = pathlib.Path(f"/proc/{pid}/status").read_text(encoding="ascii")
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    raise RuntimeError(f"VmHWM is missing for child process {pid}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes-mib",
        nargs="+",
        type=int,
        default=[64, 256, 1024],
        help="sparse input sizes in MiB (default: 64 256 1024)",
    )
    args = parser.parse_args()

    if sys.platform != "linux" or not pathlib.Path("/proc/self/status").exists():
        parser.error("this benchmark requires Linux /proc process statistics")
    if not args.sizes_mib or any(size <= 0 for size in args.sizes_mib):
        parser.error("all --sizes-mib values must be positive")

    with tempfile.TemporaryDirectory(prefix="axiom-scan-memory-") as temp_dir:
        work = pathlib.Path(temp_dir)
        scanner = work / ("axiom-scan.exe" if os.name == "nt" else "axiom-scan")
        build = subprocess.run(
            [
                sys.executable,
                str(ROOT / "bin" / "axiom"),
                "build",
                str(ROOT / "examples" / "21_axiom_scan.ax"),
                "-o",
                str(scanner),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if build.returncode:
            sys.stderr.write(build.stdout + build.stderr)
            return build.returncode

        rules = work / "no-match.yar"
        rules.write_text(
            'rule MemoryBench {\n strings:\n  $a = "NOT_PRESENT_7F19"\n'
            " condition:\n  $a\n}\n",
            encoding="utf-8",
        )

        for size_mib in args.sizes_mib:
            target = work / f"sparse-{size_mib}m.bin"
            with target.open("wb") as output:
                output.truncate(size_mib * 1024 * 1024)

            command = [str(scanner), "scan", str(target), "--rules", str(rules)]
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            start = time.monotonic()
            max_rss_kib = 0
            while process.poll() is None:
                try:
                    max_rss_kib = max(max_rss_kib, peak_rss_kib(process.pid))
                except FileNotFoundError:
                    break
                time.sleep(0.005)
            stdout, stderr = process.communicate()
            elapsed_seconds = time.monotonic() - start
            if process.returncode:
                sys.stderr.write(stdout + stderr)
                return process.returncode

            report = json.loads(stdout)
            if report.get("scanned_bytes") != size_mib * 1024 * 1024:
                raise RuntimeError("scanner report does not cover the complete input")
            print(
                json.dumps(
                    {
                        "input_mib": size_mib,
                        "scanned_bytes": report["scanned_bytes"],
                        "match_count": report["match_count"],
                        "elapsed_seconds": round(elapsed_seconds, 3),
                        "sampled_peak_rss_mib": round(max_rss_kib / 1024, 1),
                    },
                    sort_keys=True,
                )
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
