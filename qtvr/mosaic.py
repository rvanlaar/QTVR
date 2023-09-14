#!/usr/bin/env python3

# https://multimedia.cx/rpza.txt

import argparse
from pathlib import Path

from mrcrowbar.utils import to_uint32_be as FourCCB
from PIL import Image

import av

from .mr_quicktime import (
    NAVGAtom,
    QuickTime,
    get_atom,
    get_atoms,
    stblAtom,
    stcoAtom,
    stscAtom,
    stsdAtom,
    stszAtom,
    tkhdAtom,
    trakAtom,
    is_qtvr,
    QTVRType,
)

formats = {"rpza": "rpza", "rle ": "qtrle", "cine": "cinepak"}


def create_image(codec: av.codec.Codec, data: bytes) -> Image:
    p = av.Packet(data)
    frame = codec.decode(p)[0]
    return frame.to_image()


def parse_file(filename: Path):
    with open(filename, "rb") as f:
        qt = QuickTime(f.read())
    return qt


def handle_object_movies(filename, qt):
    navg_list = get_atoms(qt, NAVGAtom)
    if len(navg_list) != 1:
        print("is object movie, but wrong number of NAVGatoms")
        exit(1)

    navg = navg_list[0]
    columns: int = navg.obj.columns
    rows: int = navg.obj.rows

    print(f"Is object movie: {columns}x{rows}")

    trak_atom = get_atom(qt, trakAtom)

    trak_header = get_atom(trak_atom, tkhdAtom)
    width = int(trak_header.obj.track_width)
    height = int(trak_header.obj.track_height)

    print(f"width: {width}\nheight: {height}")
    sample_table = get_atom(trak_atom, stblAtom)
    # Note: handle samples per chunk in stsc atom
    sample_size_table = get_atom(sample_table, stszAtom).obj.sample_size_table
    chunk_offset_table = get_atom(sample_table, stcoAtom).obj.chunk_offset_table
    sample_description_table = get_atom(
        sample_table, stsdAtom
    ).obj.sample_description_table[0]

    data_format = FourCCB(sample_description_table.data_format).decode("ASCII")
    sample_description_entry = sample_description_table.atoms[0].obj
    depth = sample_description_entry.depth
    ffmpeg_codec = formats.get(data_format, None)
    if ffmpeg_codec is None:
        print(f"Unknown file format: {data_format}")
        print(f"Can only handle RPZA, cinepak and RLE movies.")
        exit(1)

    codec = av.Codec(ffmpeg_codec, "r").create()
    codec.width = width
    codec.height = height
    codec.bits_per_coded_sample = depth

    stsc = get_atom(sample_table, stscAtom).obj
    samples_per_chunk = stsc.sample_to_chunk_table[0].samples_per_chunk

    sample_chunk_table = [
        [i.first_chunk, i.samples_per_chunk] for i in stsc.sample_to_chunk_table
    ]

    chunk_offsets = [i.pointer for i in chunk_offset_table]
    sample_sizes = [i.size for i in sample_size_table]

    sample_offset = 0
    dst = Image.new("RGB", (width * columns, height * rows))

    sample_to_chunk = {}
    sample_id = 0

    # create a table with all sample_ids, matched with their chunk_id
    # set first_in_chunk to true for every new chunk_id
    for index, elem in enumerate(sample_chunk_table):
        chunk_id, samples_per_chunk = elem
        if len(sample_chunk_table) > index + 1:
            next_chunk_id, _ = sample_chunk_table[index + 1]
        else:
            next_chunk_id = len(chunk_offsets) + 1
        while chunk_id < next_chunk_id:
            samples = list(range(sample_id, sample_id + samples_per_chunk))
            first_in_chunk = True
            for sample_id in samples:
                sample_to_chunk[sample_id] = chunk_id, first_in_chunk
                first_in_chunk = False
            chunk_id += 1
            sample_id += 1

    with open(filename, "rb") as movie:
        for sample_id, sample_size in enumerate(sample_sizes):
            chunk_id, first_in_chunk = sample_to_chunk[sample_id]
            if first_in_chunk is True:
                sample_offset = 0
            chunk_offset = chunk_offsets[chunk_id - 1]
            absolute_offset = chunk_offset + sample_offset

            movie.seek(absolute_offset)
            data = movie.read(sample_size)

            image = create_image(codec, data)
            sample_offset += sample_size

            # write frame out to the destination mosaic
            column = sample_id % columns
            row = sample_id // columns
            pos = (column * width, row * height)
            dst.paste(image, pos)

    name = filename.name
    dst.save(f"mosaic-{name}.png")


def handle_panorama_movies(filename: Path, qt: QuickTime):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", metavar="FILE", type=Path, help="QTVR v1 movie")
    args = parser.parse_args()

    qt = parse_file(args.filename)
    match is_qtvr(qt):
        case QTVRType.OBJECT:
            print("detected: object movie")
            handle_object_movies(args.filename, qt)
        case QTVRType.PANORAMA:
            print("detected: panorama movie")
            handle_panorama_movies(args.filename, qt)
        case QTVRType.V2:
            print("Can't handle QTVR2 or later")
        case _:
            print("Not a QTVR 1 movie")
