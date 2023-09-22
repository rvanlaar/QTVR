#!/usr/bin/env python3

# https://multimedia.cx/rpza.txt

import argparse
from pathlib import Path

import av
from mrcrowbar.utils import to_uint32_be as FourCCB
from PIL import Image

from .mr_panorama import get_pano_track
from .mr_quicktime import (
    NAVGAtom,
    QTVRType,
    QuickTime,
    get_atom,
    get_atoms,
    is_qtvr,
    stblAtom,
    stcoAtom,
    stscAtom,
    stsdAtom,
    stszAtom,
    tkhdAtom,
    trakAtom,
)
from .qt_palette import get_palette

formats = {"rpza": "rpza", "rle ": "qtrle", "cvid": "cinepak", "smc ": "smc"}


def create_image(codec: av.codec.Codec, data: bytes) -> Image:
    p = av.Packet(data)
    frame = codec.decode(p)[0]

    if codec.name == "smc" and codec.bits_per_coded_sample == 8:
        # smc is only seen in hotspots tracks, which per definition are 8 bits

        # Frame consists of two numpy arrays.
        # first one is the frame data, second one is the palette.
        # because ffmpeg doesn't see the qt container, it doesn't know
        # which palette to use. We use the default qt 8 bit depth palette

        pal = get_palette()
        img = Image.fromarray(frame.to_ndarray()[0])
        img.putpalette(pal)
        return img

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

    export_name = f"mosaic-{filename.name}"

    create_mosaic(filename, export_name, columns, rows, trak_atom)


def create_mosaic(filename, export_name, columns, rows, trak_atom, rotate=0):
    trak_header = get_atom(trak_atom, tkhdAtom)
    width = int(trak_header.track_width)
    height = int(trak_header.track_height)

    print(f"width: {width}\nheight: {height}")
    sample_table = get_atom(trak_atom, stblAtom)
    # Note: handle samples per chunk in stsc atom
    sample_size_table = get_atom(sample_table, stszAtom).sample_size_table
    chunk_offset_table = get_atom(sample_table, stcoAtom).chunk_offset_table
    sample_description_table = get_atom(
        sample_table, stsdAtom
    ).sample_description_table[0]

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

    stsc = get_atom(sample_table, stscAtom)
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

    image_id = 0
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
            number_of_samples_in_previous_image = rows * columns * image_id
            if sample_id >= number_of_samples_in_previous_image:
                sample_id_calc = sample_id - number_of_samples_in_previous_image
            else:
                sample_id_calc = sample_id

            column = sample_id_calc % columns
            row = sample_id_calc // columns
            pos = (column * width, row * height)

            dst.paste(image, pos)
            # print(f'{row}x{column} {sample_id}')
            if ((sample_id + 1) % (rows * columns)) == 0:
                if rotate:
                    dst = dst.rotate(rotate, expand=True)
                dst.save(f"{image_id}-{export_name}.png")
                dst = Image.new("RGB", (width * columns, height * rows))
                image_id += 1


def handle_panorama_movies(filename: Path, qt: QuickTime):
    tracks = get_atoms(qt, trakAtom)
    d = {get_atom(track, tkhdAtom).track_id: track.obj for track in tracks}

    panoramic_track = get_pano_track(tracks)
    if not panoramic_track:
        print("Not a panoramic track")
        exit(1)

    sample_description = (
        get_atom(panoramic_track, stsdAtom).sample_description_table[0].atoms[0].obj
    )

    rows = sample_description.sceneNumFramesX
    columns = sample_description.sceneNumFramesY

    sceneTrack = d[sample_description.sceneTrackID]
    hotspotTrack = d[sample_description.hotSpotTrackID]

    print("handling high res track")
    export_name = f"{filename.name}-sceneTrack"
    create_mosaic(filename, export_name, rows, columns, sceneTrack, rotate=-90)

    if sample_description.loResSceneTrackID:
        print("handling lores track")
        export_name = f"{filename.name}-loressceneTrack"
        low_res_rows = max(rows // 2, 1)

        loressceneTrack = d[sample_description.loResSceneTrackID]

        create_mosaic(
            filename,
            export_name,
            low_res_rows,
            columns // 2,
            loressceneTrack,
            rotate=-90,
        )

    if sample_description.hotSpotTrackID:
        print("handling hotspot Track")
        export_name = f"{filename.name}-hotspotTrack"
        hotspotRows = sample_description.hotSpotNumFramesX
        hotspotColumns = sample_description.hotSpotNumFramesY
        create_mosaic(
            filename,
            export_name,
            hotspotRows,
            hotspotColumns,
            hotspotTrack,
            rotate=-90,
        )


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
