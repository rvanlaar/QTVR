import argparse
import subprocess
import tempfile
from pathlib import Path


from .human_sort import human_sort
from .mr_quicktime import NAVGAtom, QuickTime, ctypAtom, get_atoms, get_atom


def parse_file(filename):
    f = open(filename, "rb").read()
    return QuickTime(f)


def handle_object_movies(filename, qt):
    print("detected: object movie")
    navg_list = get_atoms(qt, NAVGAtom)
    if len(navg_list) != 1:
        print("is object movie, but wrong number of NAVGatoms")
        exit(0)

    navg = navg_list[0]
    columns: int = navg.columns
    rows: int = navg.rows

    print(f"Is object movie: {columns}x{rows}")

    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(
            ["ffmpeg", "-i", filename, f"{directory}/out%d.png"], capture_output=True
        )
        files = list(str(item) for item in Path(directory).iterdir())
        human_sort(files)
        if len(files) > columns * rows:
            # todo: check filestructure QT, is it really a thumbnail/preview
            # remove the last item, it's probably thumbnail
            files = files[:-1]
        subprocess.run(
            [
                "montage",
                *files,
                "-geometry",
                "+0+0",
                "-tile",
                f"{columns}x{rows}",
                f"mosaic-{filename.name}.png",
            ]
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", metavar="FILE", type=Path, help="QTVR v1 movie")
    args = parser.parse_args()

    qt = parse_file(args.filename)
    ctype = get_atom(qt, ctypAtom)
    if ctype is None:
        print("Not a QTVR 1 movie")
        exit(0)
    controller_id = ctype.id
    if controller_id == b"stna":
        handle_object_movies(args.filename, qt)
