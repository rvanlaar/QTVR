# https://multimedia.cx/mirror/cinepak.txt

from __future__ import annotations

from io import BufferedReader

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image


def read_int(f: BufferedReader, size: int) -> int:
    data = f.read(size)
    return int.from_bytes(data, byteorder="big")


def read_8(f: BufferedReader) -> int:
    return read_int(f, 1)


def read_short(f: BufferedReader) -> int:
    return read_int(f, 2)


@dataclass(frozen=True)
class Rect:
    top_y: int
    top_x: int
    bottom_y: int
    bottom_x: int


@dataclass(frozen=True)
class StripHeader:
    cvid_id: int
    size: int
    rect: Rect


def parse_strip_header(f: BufferedReader) -> StripHeader:
    cvid_id = read_short(f)
    strip_size = read_short(f)
    top_y = read_short(f)
    top_x = read_short(f)
    bottom_y = read_short(f)
    bottom_x = read_short(f)

    if cvid_id == 0x1000:
        _code_type = "intra-coded"
    elif cvid_id == 0x1100:
        _code_type = "inter-coded"

    # only handle itra coded or go out with a bang
    assert cvid_id == 0x1000

    print(f"{cvid_id}, {strip_size}: {top_y},{top_x},{bottom_y},{bottom_x}")

    return StripHeader(cvid_id, strip_size, Rect(top_y, top_x, bottom_y, bottom_x))


@dataclass(frozen=True)
class Block12bV4:
    y0: int
    y1: int
    y2: int
    y3: int
    u: int
    v: int

    # R = y+2*v  G = y-(u/2)-v  B = y+2*u

    def pixel(self, var: Literal["y0", "y1", "y2", "y3"]) -> tuple[int, int, int]:
        y = getattr(self, var)
        R = y + 2 * self.v
        G = y - (self.u // 2) - self.v
        B = y + 2 * self.u
        return R, G, B

    @property
    def p0(self) -> tuple[int, int, int]:
        return self.pixel("y0")

    @property
    def p1(self) -> tuple[int, int, int]:
        return self.pixel("y1")

    @property
    def p2(self) -> tuple[int, int, int]:
        return self.pixel("y2")

    @property
    def p3(self) -> tuple[int, int, int]:
        return self.pixel("y3")

    def arr(self) -> list[tuple[int, int, int]]:
        return [self.p0, self.p1, self.p2, self.p3]


code_blocks: list[Block12bV4] = []


@dataclass
class CinepakFrame:
    width: int
    height: int

    red: np.ndarray[np.uint16, np.dtype[np.float64]]
    green: np.ndarray[np.uint16, np.dtype[np.float64]]
    blue: np.ndarray[np.uint16, np.dtype[np.float64]]

    def create_img(self) -> Image.Image:
        red = Image.fromarray(self.red).convert("L")
        green = Image.fromarray(self.green).convert("L")
        blue = Image.fromarray(self.blue).convert("L")
        return Image.merge("RGB", (red, green, blue))


def parse_chunk(f, frame: CinepakFrame) -> None:
    chunk_id = read_short(f)
    size = read_short(f) - 4
    end_pos = f.tell() + size

    table = {
        0x2000: "List of blocks in 12 bit V4 codebook",
        0x2200: "List of blocks in 12 bit V1 codebook",
        0x2400: "List of blocks in 8 bit V4 codebook",
        0x2600: "List of blocks in 8 bit V1 codebook",
        0x3000: "Vectors used to encode a frame",
        0x3200: "List of blocks from only the V1 codebook",
    }
    print(f"size: {size} chunk: {table[chunk_id]}")

    # assert(chunk_id in [0x2000, 0x3000])
    if chunk_id == 0x2000:
        entries = size // 6
        for _ in range(entries):
            code_blocks.append(Block12bV4(*struct.unpack(">BBBBbb", f.read(6))))
    if chunk_id == 0x3000:
        pos_y, pos_x = 0, 0
        end_pos = f.tell() + size
        while f.tell() < end_pos:
            tmp_pos = f.tell()
            print(f"reading pos: {tmp_pos:X}")
            flags = read_int(f, 4)
            bit_string = bin(flags)[2:]
            for i in bit_string:
                if i == "1":
                    v4_x = pos_x
                    v4_y = pos_y
                    code_block_ids = [read_8(f), read_8(f), read_8(f), read_8(f)]
                    for v4_id, cb_id in enumerate(code_block_ids):
                        cb = code_blocks[cb_id]

                        for pixel_id, pixel in enumerate(cb.arr()):
                            if pixel_id == 0:
                                tmp_x = v4_x
                                tmp_y = v4_y
                            if pixel_id == 1:
                                tmp_x = v4_x + 1
                                tmp_y = v4_y
                            if pixel_id == 2:
                                tmp_x = v4_x
                                tmp_y = v4_y + 1
                            if pixel_id == 3:
                                tmp_x = v4_x + 1
                                tmp_y = v4_y + 1

                            r, g, b = pixel
                            frame.red[tmp_y, tmp_x] = r
                            frame.green[tmp_y, tmp_x] = g
                            frame.blue[tmp_y, tmp_x] = b
                        if v4_id == 0:
                            v4_x += 2
                        if v4_id == 1:
                            v4_x -= 2
                            v4_y += 2
                        if v4_id == 2:
                            v4_x += 2

                else:
                    code_block_id = read_8(f)
                    cb = code_blocks[code_block_id]
                    for pixel_id, pixel in enumerate(cb.arr()):
                        if pixel_id == 0:
                            tmp_x = pos_x
                            tmp_y = pos_y
                        if pixel_id == 1:
                            tmp_x = pos_x + 1
                            tmp_y = pos_y
                        if pixel_id == 2:
                            tmp_x = pos_x
                            tmp_y = pos_y + 1
                        if pixel_id == 3:
                            tmp_x = pos_x + 1
                            tmp_y = pos_y + 1

                        r, g, b = pixel
                        frame.red[tmp_y : tmp_y + 2, tmp_x : tmp_x + 2] = r
                        frame.green[tmp_y : tmp_y + 2, tmp_x : tmp_x + 2] = g
                        frame.blue[tmp_y : tmp_y + 2, tmp_x : tmp_x + 2] = b

                pos_x += 4
                if pos_x >= frame.width:
                    pos_x = 0
                    pos_y += 4

    cur_pos = f.tell()
    if cur_pos != end_pos:
        print(f"Current pos: {cur_pos} expected: {end_pos}")
        f.seek(end_pos)


def parse(filename: str) -> None:
    f = open(filename, "rb")
    _flags = read_int(f, 1)
    file_size = read_int(f, 3)
    width = read_int(f, 2)
    height = read_int(f, 2)
    number_coded_strips = read_int(f, 2)

    frame = CinepakFrame(
        width,
        height,
        np.zeros((height, width), dtype=np.float64),
        np.zeros((height, width), dtype=np.float64),
        np.zeros((height, width), dtype=np.float64),
    )

    # We aren't able to handle images with multiple strips
    assert number_coded_strips == 1

    print(
        f"{filename}: {width}x{height} strips: {number_coded_strips} size: {file_size}"
    )
    _header = parse_strip_header(f)

    while f.tell() < file_size:
        print(f"0x{f.tell():X}")
        parse_chunk(f, frame)

    f.close()
    img = frame.create_img()
    img.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", metavar="FILE", type=Path, help="cinepak frame")
    args = parser.parse_args()

    parse(args.filename)
