# based on https://wiki.multimedia.cx/index.php/Apple_QuickTime_RLE

from dataclasses import dataclass
from pathlib import Path
from io import BufferedReader


import numpy as np
from PIL import Image


def read_int(f: BufferedReader, size: int, signed=False) -> int:
    data = f.read(size)
    return int.from_bytes(data, byteorder="big", signed=signed)


def read_byte(f: BufferedReader) -> int:
    return read_int(f, 1)


def read_byteS(f: BufferedReader) -> int:
    return read_int(f, 1, signed=True)


@dataclass
class RLEFrame:
    width: int
    height: int

    surface: np.array
    pos_x: int = 0
    pos_y: int = 0

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.surface = np.zeros((height, width, 3), dtype=np.uint8)

    def skip_pixels(self, skip: int):
        self.pos_x += skip

    def next_pixel(self):
        self.pos_x += 1
        if not (self.pos_x <= self.width):
            print("ERROR: continue anyway")

    def next_line(self):
        self.pos_x = 0
        self.pos_y += 1

    def set_pixel(self, R:int, G: int, B: int):
        self.surface[self.pos_y: self.pos_y+1, self.pos_x: self.pos_x+1] = [R, G, B]
        self.next_pixel()

    def create_img(self):
        return Image.fromarray(self.surface, mode="RGB")

    def show(self):
        self.create_img().show()


def create_image_rle(
    filename: Path,
    sample_size: int,
    sample_offset: int,
    width: int,
    height: int,
    depth: int,
):
    frame = RLEFrame(width, height)
    f = open(filename, "rb")
    f.seek(sample_offset)
    f.read(1)  # unknown flags
    chunk_size = read_int(f, 3)
    assert chunk_size == sample_size, "chunk size isn't equal to the sample size"

    assert depth == 24, "Only handles depth of 24bits"

    header = read_int(f, 2)
    if header == 0x8:
        start_line = read_int(f, 2)
        frame.pos_y = start_line

        f.read(2)  # unknown
        number_of_lines_to_update = read_int(f, 2)  # number of lines to update
        f.read(2)  # unkown

        #print(f"lines: {number_of_lines_to_update}")
        for i in range(number_of_lines_to_update):
            skip_count = read_byte(f)
            #print(f"skip: {skip_count}")
            frame.skip_pixels(skip_count - 1)

            rle_code = read_byteS(f)
            #print(f"rle_code: {rle_code}")

            while rle_code != -1:
                # another single-byte skip code in the stream
                if rle_code == 0:
                    skip_count = read_byteS(f)
                    frame.skip_pixels(skip_count - 1) 
                if rle_code > 0:
                    count = rle_code
                    for _ in range(count):
                        R, G, B = read_byte(f), read_byte(f), read_byte(f)
                        frame.set_pixel(R, G, B)
                if rle_code < -1:
                    R, G, B = read_byte(f), read_byte(f), read_byte(f)
                    count =-rle_code
                    for _ in range(count):
                        frame.set_pixel(R, G, B)
                rle_code = read_byteS(f)
                #print(f"rle_code: {rle_code}")
            frame.next_line()

        return frame
