#!/usr/bin/env python3

# https://multimedia.cx/rpza.txt

import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path

import numpy as np
from mrcrowbar.utils import to_uint32_be as FourCCB
from PIL import Image

from human_sort import human_sort
from mr_quicktime import (
    NAVGAtom,
    QuickTime,
    ctypAtom,
    get_atom,
    get_atoms,
    stblAtom,
    stcoAtom,
    stscAtom,
    stsdAtom,
    stszAtom,
    tkhdAtom,
    trakAtom,
)


@dataclass
class RPZAFrame:
    width: int
    height: int

    surface: np.array
    pos_x: int = 0
    pos_y: int = 0
    current_block: int = 0

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.surface = np.zeros(
            (height, width, 3), dtype=np.uint8
        )

    def next_block(self):
        if self.current_block >= self.total_blocks:
            print("out of bounds")  # don't advance
            return
        self.pos_x += 4
        if self.pos_x >= self.width:
            self.pos_x = 0
            self.pos_y += 4
        self.current_block += 1
        #print(f"advanced to block {self.current_block}: {self.pos_x}, {self.pos_y}")

    @property
    def total_blocks(self):
        return (self.width // 4) * (self.height // 4)

    def create_img(self):
        return Image.fromarray(self.surface, mode="RGB")
    
    @property
    def show(self):
        self.create_img().show()


def read_int(f: BufferedReader, size: int) -> int:
    data = f.read(size)
    return int.from_bytes(data, byteorder="big")


def read_byte(f: BufferedReader) -> int:
    return read_int(f, 1)


def parse_file(filename: Path):
    f = open(filename, "rb").read()
    return QuickTime(f)


def color_to_rbg(color: int):
    color = color & 0x7FFF
    red = (color >> 10) << 3
    green = ((color >> 5) & 0x1F) << 3
    blue = (color & 0x1F) << 3
    return [red, green, blue]


def create_image_rpza(
    filename: Path, sample_size: int, sample_offset: int, width: int, height: int
):
    frame = RPZAFrame(width, height)

    f = open(filename, "rb")
    f.seek(sample_offset)
    first_byte = read_byte(f) == 0xE1  # First byte is always 0xe1
    if not first_byte:
        breakpoint()
    chunk_len = read_int(f, 3)
    if chunk_len != sample_size:
        breakpoint()
        
    end_of_chunk = sample_offset + chunk_len
    while f.tell() < end_of_chunk:
        opcode_block = read_byte(f)
        num_blocks = (opcode_block & 0x1F) + 1
        printable_opcode = opcode_block & 0xE0
        #print(f"0x{printable_opcode:X} blocks: {num_blocks}")
        
        if (opcode_block & 0x80) == 0:
            colorA = (opcode_block << 8) | read_byte(f)
            opcode_block = 0
            pre_peek_pos = f.tell()
            peek = read_byte(f)
            f.seek(pre_peek_pos)
            if (peek & 0x80):
                opcode_block = 0x20   
                #print(f"new opcode: 0x{opcode:X}")
                num_blocks = 1

        opcode = opcode_block & 0xE0
        table = {
            0x80: "skip blocks",
            0xA0: "Fill with one color",
            0xC0: "Fill blocks with 4 colors",
            0x20: "Fill blocks with 4 colors",
            0x00: "Fill blocks with 16 colors",
        }

        if opcode not in (0x80, 0xA0, 0xC0, 0x20, 0x00):
            breakpoint()

        #print(table[opcode])

        if opcode == 0x80:  # skip blocks
            while num_blocks > 0:
                frame.next_block()
        if opcode == 0xA0:  # fill with one color
            colorA = read_int(f, 2) & 0x7FFF
            true_colorA = color_to_rbg(colorA)
            while num_blocks > 0:
                x = frame.pos_x
                y = frame.pos_y
                frame.surface[y : y + 4, x : x + 4] = true_colorA
                frame.next_block()
                num_blocks -= 1
        if opcode == 0xC0:  # Fill blocks with 4 colors
            colorA = read_int(f, 2)
        if opcode in (0x20, 0xC0):  # fill blocks with 4 colors
            colorB = read_int(f, 2)
            color_table = [colorB & 0x7FFF, 0, 0, colorA & 0x7FFF]

            # Red components
            ta = (colorA >> 10) & 0x1F
            tb = (colorB >> 10) & 0x1F
            color_table[1] |= ((11 * ta + 21 * tb) >> 5) << 10
            color_table[2] |= ((21 * ta + 11 * tb) >> 5) << 10

            # Green components
            ta = (colorA >> 5) & 0x1F
            tb = (colorB >> 5) & 0x1F
            color_table[1] |= ((11 * ta + 21 * tb) >> 5) << 5
            color_table[2] |= ((21 * ta + 11 * tb) >> 5) << 5

            # Blue components
            ta = colorA & 0x1F
            tb = colorB & 0x1F
            color_table[1] |= (11 * ta + 21 * tb) >> 5
            color_table[2] |= (21 * ta + 11 * tb) >> 5

            true_color_table = [color_to_rbg(color) for color in color_table]

            color_ids = []
            for _ in range(4):
                flags = read_byte(f)
                color_ids.extend(
                    [
                        flags >> 6 & 0x03,
                        flags >> 4 & 0x03,
                        flags >> 2 & 0x03,
                        flags >> 0 & 0x03,
                    ]
                )
            while num_blocks > 0:
                x = frame.pos_x
                y = frame.pos_y
                for i, color_id in enumerate(color_ids):
                    x_offset = x + i % 4
                    y_offset = y + i // 4
                    frame.surface[
                        y_offset : y_offset + 1, x_offset : x_offset + 1
                    ] = true_color_table[color_id]
                frame.next_block()
                num_blocks -= 1

        if opcode == 0x00:  # fill blocks with 16 colors
            colors = [colorA]
            for _ in range(15):
                colors.append(read_int(f, 2))
            x = frame.pos_x
            y = frame.pos_y
            true_colors = [color_to_rbg(color) for color in colors]
            for i, color in enumerate(true_colors):
                x_offset = x + i % 4
                y_offset = y + i // 4
                frame.surface[y_offset : y_offset + 1, x_offset : x_offset + 1] = color
            frame.next_block()

    return frame


def handle_object_movies(filename, qt):
    print("detected: object movie")
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

    sample_table = get_atom(trak_atom, stblAtom)
    # Note: handle samples per chunk in stsc atom
    sample_size_table = get_atom(sample_table, stszAtom).obj.sample_size_table
    chunk_offset_table = get_atom(sample_table, stcoAtom).obj.chunk_offset_table
    sample_description_table = get_atom(
        sample_table, stsdAtom
    ).obj.sample_description_table[0]

    data_format = FourCCB(sample_description_table.data_format).decode("ASCII")
    if data_format != "rpza":
        print(f"Can only handle rpza object movies: {data_format}")
        exit(1)

    stsc = get_atom(sample_table, stscAtom).obj
    samples_per_chunk = stsc.sample_to_chunk_table[0].samples_per_chunk

    sample_chunk_table = [[i.first_chunk, i.samples_per_chunk] for i in stsc.sample_to_chunk_table]

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

    for sample_id, sample_size in enumerate(sample_sizes):
        chunk_id, first_in_chunk = sample_to_chunk[sample_id]
        if first_in_chunk is True:
            sample_offset = 0
        chunk_offset = chunk_offsets[chunk_id - 1]
        total_offset = chunk_offset + sample_offset
        frame = create_image_rpza(filename, sample_size, total_offset, width, height)
        sample_offset += sample_size

        # write frame out to the destination mosaic
        column = sample_id % columns
        row = sample_id // columns
        pos = (column * width, row * height)
        dst.paste(frame.create_img(), pos)

    name = filename.name
    dst.save(f"mosaic-{name}.png")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", metavar="FILE", type=Path, help="QTVR v1 movie")
    args = parser.parse_args()

    qt = parse_file(args.filename)
    ctype = get_atom(qt, ctypAtom)
    controller_id = FourCCB(ctype.obj.id)
    if controller_id == b"stna":
        handle_object_movies(args.filename, qt)


if __name__ == "__main__":
    main()
