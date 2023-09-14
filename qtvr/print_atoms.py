import argparse
from pathlib import Path

from . import mr_quicktime

from .mr_quicktime import QuickTime, stblAtom


def print_unkown_fourccs():
    if mr_quicktime.UNKNOWN_FOURCC:
        print("Unknown FourCCs:")
    for el in mr_quicktime.UNKNOWN_FOURCC:
        print(el)


stsd = []


def print_atom(atom, indent=0):
    indent_str = ">" * indent
    print(f"{indent_str}{atom}")
    if hasattr(atom, "obj") and isinstance(atom.obj, stblAtom):
        stsd.append(atom)
    if hasattr(atom, "atoms"):
        for el in atom.atoms:
            print_atom(el, indent + 1)
    if hasattr(atom, "obj") and hasattr(atom.obj, "atoms"):
        for el in atom.obj.atoms:
            print_atom(el, indent + 1)


def simply_structure(qt: QuickTime):
    k = dict()
    for atom in qt.atoms:
        name = atom.obj.__class__.__name__
        k[name] = atom
    return k


def parse_file(filename):
    f = open(filename, "rb").read()
    return QuickTime(f)


def create_image(entries, offsets, sizes, filename):
    """Create files of QT image samples"""
    f = open(filename, "rb")

    for i in range(entries):
        offset = offsets[i].pointer
        size = sizes[i].size
        f.seek(offset)
        data = f.read(size)
        with open(f"nav_{i}.cinepak", "wb") as to_file:
            to_file.write(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", metavar="FILE", type=Path, help="QT Movie filename")
    args = parser.parse_args()
    print(f"filename: {args.filename}")
    qt = parse_file(args.filename)

    print_atom(qt)
    print_unkown_fourccs()
