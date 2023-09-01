from dataclasses import dataclass
from io import BufferedReader
from pathlib import Path

import numpy as np
from PIL import Image


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
        self.surface = np.zeros((height, width, 3), dtype=np.uint8)

    def next_block(self):
        if self.current_block >= self.total_blocks:
            print("out of bounds")  # don't advance
            return
        self.pos_x += 4
        if self.pos_x >= self.width:
            self.pos_x = 0
            self.pos_y += 4
        self.current_block += 1
        # print(f"advanced to block {self.current_block}: {self.pos_x}, {self.pos_y}")

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
        # print(f"0x{printable_opcode:X} blocks: {num_blocks}")

        if (opcode_block & 0x80) == 0:
            colorA = (opcode_block << 8) | read_byte(f)
            opcode_block = 0
            pre_peek_pos = f.tell()
            peek = read_byte(f)
            f.seek(pre_peek_pos)
            if peek & 0x80:
                opcode_block = 0x20
                # print(f"new opcode: 0x{opcode:X}")
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

        # print(table[opcode])

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
