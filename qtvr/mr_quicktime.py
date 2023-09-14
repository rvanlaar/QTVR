"""
MrCrowbar file for Quicktime movies

Specifiation is from: QuickTime File Format Specification
https://multimedia.cx/mirror/qtff-2007-09-04.pdf
"""

import struct

from typing import TypeVar

from mrcrowbar import models as mrc
from mrcrowbar.utils import from_uint32_be as FourCC
from mrcrowbar.utils import to_uint32_be as FourCCB


class AppleFloatField(mrc.Field):
    def __init__(self, offset):
        default = []
        super().__init__(default=default)
        self.offset = offset

    def get_from_buffer(self, buffer, parent=None):
        offset = self.offset
        a = struct.unpack(">h", buffer[offset : offset + 2])[0]
        # TODO: is b signed or unsigned?
        b = struct.unpack(">H", buffer[offset + 2 : offset + 4])[0]
        return a + b / 65536


class ContainerAtom(mrc.Block):
    atoms = mrc.ChunkField(
        mrc.Ref("CHUNK_MAP"),
        0x00,
        id_field=mrc.UInt32_BE,
        length_field=mrc.UInt32_BE,
        default_klass=mrc.Unknown,
        length_before_id=True,
        length_inclusive=True,
    )


UNKNOWN_FOURCC = set()


def create_knowntype(key, base_class=mrc.Unknown):
    fourcc = make_fourcc(key)
    UNKNOWN_FOURCC.add(fourcc)
    return type(f"{fourcc}-Unknown", (base_class,), {})


def make_fourcc(key):
    if not isinstance(key, int):
        return False
    try:
        return FourCCB(key).decode()
    except UnicodeDecodeError:
        return False


class mrcdict(dict):
    def __getitem__(self, key):
        retval = super().__getitem__(key)
        return retval

    def __contains__(self, key):
        if make_fourcc(key):
            return True

        retval = super().__contains__(key)
        return retval

    def __missing__(self, key):
        return create_knowntype(key)


class mrcdict(dict):
    pass


# fmt: off
class mvhdAtom(mrc.Block):
    """
    MoVieHeaDer

    Specifies characteristics of the entire QuickTime movie.
    #//apple_ref/doc/uid/TP40000939-CH204-BBCGFGJG
    """
    version =               mrc.UInt8(0x00)
    flags =                 mrc.Bytes(0x01, length=3)

    # time in seconds since midnight January 1, 1904
    creation_time =         mrc.UInt32_BE(0x04)
    modification_time =     mrc.UInt32_BE(0x08)
    # the number of time units that pass per second
    time_scale =            mrc.UInt32_BE(0x0C)
    # duration of the movie in timescale units
    duration =              mrc.UInt32_BE(0x10)
    # fixed point number, a value of 1.0 indicates normal rate
    preferred_rate =        mrc.UInt32_BE(0x14)
    # fixed point number, a value of 1.0 indicates full volume
    preferred_volume =      mrc.UInt16_BE(0x18)
    reserved =              mrc.Bytes(0x1A, length=10)
    matrix_structure =      mrc.Bytes(0x24, length=36)
    preview_time =          mrc.UInt32_BE(0x48)
    preview_duration =      mrc.UInt32_BE(0x4C)
    poster_time =           mrc.UInt32_BE(0x50)
    selection_time =        mrc.UInt32_BE(0x54)
    selection_duration =    mrc.UInt32_BE(0x58)
    current_time =          mrc.UInt32_BE(0x5C)
    next_track_id =         mrc.UInt32_BE(0x60)


class tkhdAtom(mrc.Block):
    """
    TracKHeaDer

    #//apple_ref/doc/uid/TP40000939-CH204-BBCEIDFA
    """
    version              = mrc.UInt8(0x0)
    track_in_poster      = mrc.Bits(0x03, 0b1000)
    track_in_preview     = mrc.Bits(0x03, 0b0100)
    track_in_movie       = mrc.Bits(0x03, 0b0010)
    track_enabled        = mrc.Bits(0x03, 0b0001)
    creation_time        = mrc.UInt32_BE(0x4)
    modification_time    = mrc.UInt32_BE(0x8)
    track_id             = mrc.UInt32_BE(0xc)
    reserved             = mrc.UInt32_BE(0x10)
    duration             = mrc.UInt32_BE(0x14)
    reserved             = mrc.Bytes(0x18, length=8)
    layer                = mrc.UInt16_BE(0x20)
    alternate_group      = mrc.UInt16_BE(0x22)
    volume               = mrc.UInt16_BE(0x24)
    reserved             = mrc.UInt16_BE(0x26)
    matrix_structure     = mrc.Bytes(0x28, length=36)
    track_width          = AppleFloatField(0x4c)
    track_height         = AppleFloatField(0x50)


class mdatAtom(mrc.Block):
    data = mrc.Bytes()


class mdhdAtom(mrc.Block):
    version              = mrc.UInt8(0x00)
    flags                = mrc.Bytes(0x01, length=3)
    creation_time        = mrc.UInt32_BE(0x04)
    modification_time    = mrc.UInt32_BE(0x08)
    time_scale           = mrc.UInt32_BE(0x0C)
    duration             = mrc.UInt32_BE(0x10)
    language             = mrc.UInt16_BE(0x14)
    quality              = mrc.UInt16_BE(0x16)


class hdlrAtom(mrc.Block):
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    component_type           = mrc.UInt32_BE(0x04)
    component_subtype        = mrc.UInt32_BE(0x08)
    component_manufacturer   = mrc.UInt32_BE(0x0C)
    component_flags          = mrc.UInt32_BE(0x10)
    component_flags_mask     = mrc.UInt32_BE(0x14)
    component_name           = mrc.Bytes(0x18)

    @property
    def repr(self):
        ct = FourCCB(self.component_type)
        cst = FourCCB(self.component_subtype)
        cm = FourCCB(self.component_manufacturer)
        cf = FourCCB(self.component_flags)
        cfm = FourCCB(self.component_flags_mask)
        # component name is a pascal string
        cn = self.component_name[1:].decode()
        return (f"Version={self.version}, flags={self.flags}, "
                f"Component Type={ct}, component SubType={cst}, "
                f"Component Manufacturer={cm}, Component Flags={cf}, "
                f"Component Flags Mask={cfm}, Component Name={cn}")

class smhdAtom(mrc.Block):
    """
    SoundMedia HeaDer
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    balance                  = mrc.UInt16_BE(0x04)
    reserved                 = mrc.UInt16_BE(0x06)


class vmhdAtom(mrc.Block):
    """
    VideoMedia HeaDer
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)

    # Graphics mode table is defined here:
    #
    # #//apple_ref/doc/uid/TP40000939-CH206-TPXREF104
    graphics_mode            = mrc.UInt16_BE(0x04)
    opcolor                  = mrc.Bytes(0x06, length=6)


class EditListTableEntry(mrc.Block):
    track_duration           = mrc.Int32_BE(0x00)
    media_time               = mrc.Int32_BE(0x04)
    media_rate               = mrc.Int32_BE(0x08)


class elstAtom(mrc.Block):
    """
    EditLiST
    """

    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    edit_list_table          = mrc.BlockField(EditListTableEntry, 0x08, count=mrc.Ref("number_of_entries"))


class drefSubAtom(mrc.Block):
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    data                     = mrc.Bytes(0x05)


class drefAtom(mrc.Block):
    """
    Data REFerance Atom
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"alis"): drefSubAtom,
        FourCC(b"rsrc"): drefSubAtom,
        FourCC(b"url "): drefSubAtom
    }
    CHUNK_MAP.update(MAPPING)

    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    atoms = mrc.ChunkField(
        mrc.Ref("CHUNK_MAP"),
        0x08,
        id_field=mrc.UInt32_BE,
        length_field=mrc.UInt32_BE,
        default_klass=drefSubAtom,
        length_before_id=True,
        length_inclusive=True,
    )

class ChunkOffsetTableEntry(mrc.Block):
    pointer                  = mrc.Int32_BE(0x00)

class stcoAtom(mrc.Block):
    """
    Chunk Offset
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    chunk_offset_table       = mrc.BlockField(ChunkOffsetTableEntry, 0x08, count=mrc.Ref("number_of_entries"))


class SampleDescriptionTable(mrc.Block):
    size                     = mrc.UInt32_BE(0x00)
    data_format              = mrc.UInt32_BE(0x04)
    reserved                 = mrc.Bytes(0x08, length=6) # zero
    data_reference_index     = mrc.UInt16_BE(0x0E)

    version                  = mrc.UInt16_BE(0x10)
    revision                 = mrc.UInt16_BE(0x12)
    vendor                   = mrc.UInt32_BE(0x14)
    temporal_quality         = mrc.UInt32_BE(0x18)
    spatial_quality          = mrc.UInt32_BE(0x1C)
    width                    = mrc.UInt16_BE(0x20)
    height                   = mrc.UInt16_BE(0x22)
    horiz_resolution         = AppleFloatField(0x24) # pixels per inch
    vert_resolution          = AppleFloatField(0x28) # pixels per inch
    reserved                 = mrc.Bytes(0x2C, length=4)
    frame_count_per_sample   = mrc.UInt16_BE(0x30)
    compressor_name_size     = mrc.UInt8(0x32)
    compressor_name          = mrc.Bytes(0x33, length=mrc.Ref("compressor_name_size"))
    depth                    = mrc.UInt16_BE(0x52)
    colorTableId             = mrc.Int16_BE(0x54)


class stsdAtom(mrc.Block):
    """
    Sample description

    ## todo: check if data_format is in sample_description table and contains qtvr
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    sample_description_table = mrc.BlockField(SampleDescriptionTable, 0x08, count=mrc.Ref("number_of_entries"))

# TODO: create sample_to_chunk_table

class SampleToChunkTable(mrc.Block):
    first_chunk              = mrc.UInt32_BE(0x00)
    samples_per_chunk        = mrc.UInt32_BE(0x04)
    sample_description       = mrc.UInt32_BE(0x08)

class stscAtom(mrc.Block):
    """
    SampleTable Sample to Chunk
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    sample_to_chunk_table    = mrc.BlockField(SampleToChunkTable, 0x08, count=mrc.Ref("number_of_entries"))

class sttsAtom(mrc.Block):
    """
    SampleTable Time to Sample
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    time_to_sample_table     = mrc.Bytes(0x08)

class stssAtom(mrc.Block):
    """
    SampleTable SyncSample

    Identifies the key frames
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    sync_sample_table        = mrc.Bytes(0x08)

class SampleSizeTableEntry(mrc.Block):
    size                     = mrc.Int32_BE(0x00)

class stszAtom(mrc.Block):
    """
    SampleTable Sample siZe
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    sample_size              = mrc.UInt32_BE(0x04)
    number_of_entries        = mrc.UInt32_BE(0x08)
    sample_size_table        = mrc.BlockField(SampleSizeTableEntry, 0x0C, count=mrc.Ref("number_of_entries"))

class NAVGAtom(mrc.Block):
    """
    NAVG atom

    https://web.archive.org/web/20001121222600/http://developer.apple.com/technotes/tn/tn1036.html
    """
    version                  = mrc.UInt16_BE(0x00) # always 1
    columns                  = mrc.UInt16_BE(0x02) # number of columns in movie
    rows                     = mrc.UInt16_BE(0x04) # number of rows in movie
    reserved                 = mrc.UInt16_BE(0x06) # zero
    loop_size                = mrc.UInt16_BE(0x08) # number of frames shot at each position
    frame_duration           = mrc.UInt16_BE(0x0A) # The duration of each frame

    # MovieType values
    # kStandardObject: 1
    # kOldNavigableMovieScene: 2
    # kObjectInScene: 3
    movie_type               = mrc.UInt16_BE(0x0C)
    loop_ticks               = mrc.UInt16_BE(0x0E) # number of ticks before next frame of loop is displayed

    # 180.0 for kStandardObject or kObjectInScene,
    # actual degrees for kOldNavigableMovieScene.
    field_of_view            = AppleFloatField(0x10)
    startHPan                = AppleFloatField(0x14) # start horizontal pan angle in degrees
    endHPan                  = AppleFloatField(0x18) # end horizontal pan angle in degrees
    endVPan                  = AppleFloatField(0x1C) # end vertical pan angle in degrees
    startVPan                = AppleFloatField(0x20) # start vertical pan angle in degrees
    initialHPan              = AppleFloatField(0x24) # initial horizontal pan angle in degrees (poster view)
    initialVPan              = AppleFloatField(0x28) # initial vertical pan angle in degrees (poster view)
    reserved2                = mrc.UInt32_BE(0x2C) # Zro


class gmhdAtom(mrc.Block):
    """
    base Media inforation HeaDer

    Indicates that this media information atom pertains to a base media
    """
    pass

# fmt: on


class dinfAtom(ContainerAtom):
    """
    DataINFormation
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"dref"): drefAtom,
    }
    CHUNK_MAP.update(MAPPING)


class stblAtom(ContainerAtom):
    """
    Sample TaBLE
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"stco"): stcoAtom,
        FourCC(b"stsc"): stscAtom,
        FourCC(b"stsd"): stsdAtom,
        FourCC(b"stts"): sttsAtom,
        FourCC(b"stsz"): stszAtom,
        FourCC(b"stss"): stssAtom,
    }

    CHUNK_MAP.update(MAPPING)


class minfAtom(ContainerAtom):
    """
    MedINFormation

    Store handler-specific information for a track's media data.
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"hdlr"): hdlrAtom,
        FourCC(b"dinf"): dinfAtom,
        FourCC(b"stbl"): stblAtom,
        FourCC(b"smhd"): smhdAtom,
        FourCC(b"vmhd"): vmhdAtom,
        FourCC(b"gmhd"): gmhdAtom,
    }
    CHUNK_MAP.update(MAPPING)


class edtsAtom(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {FourCC(b"elst"): elstAtom}
    CHUNK_MAP.update(MAPPING)


class mdiaAtom(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"mdhd"): mdhdAtom,
        FourCC(b"hdlr"): hdlrAtom,
        FourCC(b"minf"): minfAtom,
    }
    CHUNK_MAP.update(MAPPING)


class trakAtom(ContainerAtom):
    """
    Track Atom

    Defines a single track of a movie.
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"mdia"): mdiaAtom,
        FourCC(b"tkhd"): tkhdAtom,
        FourCC(b"edts"): edtsAtom,
    }
    CHUNK_MAP.update(MAPPING)


class ctypAtom(mrc.Block):
    """
    Controller TYPe
    """

    id = mrc.UInt32_BE(0x00)

    @property
    def repr(self):
        _id = FourCCB(self.id).decode()
        return f"id={_id}"


class WLOCAtom(mrc.Block):
    """
    Window LOCation
    """

    x = mrc.UInt16_BE(0x00)
    y = mrc.UInt16_BE(0x02)


class udtaAtom(mrc.Block):
    """
    User DaTA Atom
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"ctyp"): ctypAtom,
        FourCC(b"WLOC"): WLOCAtom,
        FourCC(b"NAVG"): NAVGAtom,
    }
    CHUNK_MAP.update(MAPPING)

    atoms = mrc.ChunkField(
        mrc.Ref("CHUNK_MAP"),
        0x00,
        id_field=mrc.UInt32_BE,
        length_field=mrc.UInt32_BE,
        default_klass=mrc.Unknown,
        length_before_id=True,
        length_inclusive=True,
        stream_end=b"\x00\x00\x00\x00",
    )
    # For historical reasons, the data list is optionally terminated by a 32-bit integer set to 0


class freeAtom(mrc.Block):
    """
    Free space in the file
    """
    free = mrc.Bytes()

class moovAtom(ContainerAtom):
    """
    moov

    #//apple_ref/doc/uid/TP40000939-CH204-55911
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"mvhd"): mvhdAtom,
        FourCC(b"trak"): trakAtom,
        FourCC(b"udta"): udtaAtom,
    }
    CHUNK_MAP.update(MAPPING)


class QuickTime(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"mdat"): mdatAtom,
        FourCC(b"moov"): moovAtom,
        FourCC(b"free"): freeAtom,
    }
    CHUNK_MAP.update(MAPPING)

T = TypeVar("T")

def get_atoms(atom, atom_kls: type[T]) -> list[T]:
    atoms = []
    if isinstance(atom, atom_kls):
        atoms.append(atom)
    if hasattr(atom, "atoms"):
        for parent_atom in atom.atoms:
            atoms.extend(get_atoms(parent_atom, atom_kls))
    if hasattr(atom, "obj"):
        if isinstance(atom.obj, atom_kls):
            atoms.append(atom)
        if hasattr(atom.obj, "atoms"):
            for parent_atom in atom.obj.atoms:
                atoms.extend(get_atoms(parent_atom, atom_kls))
    return atoms

from enum import IntEnum, auto

def get_atom(atom: mrc.Block, atom_kls: type[T]) -> T:
    atoms = get_atoms(atom, atom_kls)
    assert len(atoms) == 1
    return atoms[0]


class QTVRType(IntEnum):
    PANORAMA = auto()
    OBJECT = auto()

def is_qtvr(atom: mrc.Block) -> QTVRType | None:
    ctyp = get_atom(atom, ctypAtom)
    controller_id = FourCCB(ctyp.obj.id)
    if controller_id == b"stna":
        return QTVRType.OBJECT
    if controller_id in (b"stpn", b"STpn"):
        return QTVRType.PANORAMA
    return None
