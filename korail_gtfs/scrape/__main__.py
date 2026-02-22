# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import IO

from . import read


@contextmanager
def _output_file(path: str | None) -> Generator[IO[str], None, None]:
    """Context-manager wrapper that opens a file at the provided path
    for writing, unless that path is None or exactly `-`, in which case sys.stdout is returned.
    """
    match path:
        case "-" | None:
            yield sys.stdout
        case _:
            with open(path, "w", encoding="utf-8") as f:
                yield f


if __name__ == "__main__":
    import argparse
    import json

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-o",
        "--output",
        metavar="JSONL_PATH",
        help="path to output .jsonl file",
    )
    arg_parser.add_argument(
        "input",
        nargs="+",
        metavar="XLSX_PATH",
        help="path to input .xlsx files",
    )
    args = arg_parser.parse_args()

    with _output_file(args.output) as f:
        for input_filename in args.input:
            for train in read.xlsx(input_filename):
                json.dump(train.as_json(), f, ensure_ascii=False)
                f.write("\n")
