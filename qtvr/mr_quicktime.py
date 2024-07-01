"""
MrCrowbar file for Quicktime movies

Specifiation is from: QuickTime File Format Specification
https://multimedia.cx/mirror/qtff-2007-09-04.pdf
"""

import struct
from typing import Any, TypeVar
from enum import IntEnum, auto

from mrcrowbar import models as mrc
from mrcrowbar.utils import to_uint32_be as FourCCB

from fractions import Fraction


class FixedFractionField(mrc.Field):
    """
    Apple used a 32 bit Fixed fraction field.
    the first 16 bits are the integer
    the last 16 bits the part behind the comma.
    i.e. divide by 65536.

    Mathematically this is the equivalent of dividing the
    whole 32 bits by 0x10000 (65536).
    """

    def __init__(self, offset):
        default = []
        super().__init__(default=default)
        self.offset = offset

    def get_from_buffer(self, buffer, parent=None):
        offset = self.offset
        fixed = struct.unpack(">i", buffer[offset : offset + 4])[0]
        return float(Fraction(fixed, 0x10000))


class GobbleAtom(mrc.Block):
    """
    An atom that gobbles the whole atom.

    This makes it possible to continue parsing atoms which are known
    after an unkown atom.
    """

    data = mrc.Bytes()


class ContainerAtom(mrc.Block):
    CHUNK_MAP: dict
    atoms: list[mrc.Chunk] = mrc.ChunkField(  # pyright: ignore[reportAssignmentType]
        mrc.Ref("CHUNK_MAP"),  # pyright: ignore[reportArgumentType]
        0x00,
        id_size=4,
        length_field=mrc.UInt32_BE,
        default_klass=GobbleAtom,
        length_before_id=True,
        length_inclusive=True,
    )


UNKNOWN_FOURCC = set()


def create_knowntype(key, base_class: type[mrc.Block] = GobbleAtom) -> type[mrc.Block]:
    """
    Register unkown atom name and create a class for it
    """
    fourcc = make_fourcc(key)
    UNKNOWN_FOURCC.add(fourcc)
    return type(f"{fourcc}-Unknown", (base_class,), {})


def make_fourcc(key: Any) -> str | None:
    if not isinstance(key, bytes):
        return None
    try:
        return key.decode()
    except UnicodeDecodeError:
        return None


class mrcdict(dict):
    """
    Dict which creates missing elements as `base_class`.

    It's purpose is to be able to register unkown atoms and continue
    parsing when encountering an unknown atom.

    From a technical perspective:

    mrc does:
        if key in dict:
            default_klass = dict[key]
    Python handles this as:
        dict.__contains__(key)
            -> which in our case returns True for a valid FourCC.
        dict.__getitem__(key)
            -> returns the value if there
            -> if it doesn't find the key it executes:
        dict.__missing__(key)
            -> which returns a base_class with the key as its name
    """

    base_class: type[mrc.Block] = GobbleAtom

    def __contains__(self, key):
        """
        Fake having an item when the key is a valid fourCC.
        """

        if make_fourcc(key) is not None:
            return True
        retval = super().__contains__(key)
        return retval

    def __missing__(self, key):
        """
        When encountering a key we don't know about, fake one and continue.
        """
        return create_knowntype(key, self.base_class)


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
    track_width          = FixedFractionField(0x4c)
    track_height         = FixedFractionField(0x50)


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


class drefSubContainer(ContainerAtom):
    CHUNK_MAP = mrcdict()
    CHUNK_MAP.base_class = drefSubAtom
    MAPPING = {
        b"alis": drefSubAtom,
        b"rsrc": drefSubAtom,
        b"url ": drefSubAtom
    }
    CHUNK_MAP.update(MAPPING)

    atoms = mrc.ChunkField( # pyright: ignore[reportAssignmentType]
        mrc.Ref("CHUNK_MAP"), # pyright: ignore[reportArgumentType]
        0x00,
        id_size=4,
        length_field=mrc.UInt32_BE,
        default_klass=drefSubAtom,
        length_before_id=True,
        length_inclusive=True,
    )


class drefAtom(mrc.Block):
    """
    Data REFerance Atom

    #ToDo: map out entries
    """

    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    drefs                    = mrc.BlockField(drefSubContainer, 0x08, count=mrc.Ref("number_of_entries"))

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


class VideoSampleDescriptionTableEntry(mrc.Block):
    reserved                 = mrc.Bytes(0x00, length=6) # zero
    data_reference_index     = mrc.UInt16_BE(0x06)

    version                  = mrc.UInt16_BE(0x08)
    revision                 = mrc.UInt16_BE(0x0A)
    vendor                   = mrc.UInt32_BE(0x0C)
    temporal_quality         = mrc.UInt32_BE(0x14)
    spatial_quality          = mrc.UInt32_BE(0x1C)

    width                    = mrc.UInt16_BE(0x18)
    height                   = mrc.UInt16_BE(0x1A)
    horiz_resolution         = FixedFractionField(0x1C) # pixels per inch
    vert_resolution          = FixedFractionField(0x20) # pixels per inch
    reserved                 = mrc.Bytes(0x24, length=4)
    frame_count_per_sample   = mrc.UInt16_BE(0x28)
    compressor_name_size     = mrc.UInt8(0x2A)
    compressor_name          = mrc.Bytes(0x2B, length=mrc.Ref("compressor_name_size"))
    depth                    = mrc.UInt16_BE(0x4A)
    colorTableId             = mrc.Int16_BE(0x4C)


class PanoSampleDescriptionTableEntry(mrc.Block):
    """
    Panorama Track Sample Description

    Source: https://developer.apple.com/library/archive/technotes/tn/tn1035.html
    """
    reserved1                = mrc.UInt32_BE(0x00)
    reserved2                = mrc.UInt32_BE(0x04) # must be zero, also observed to be 1
    majorVersion             = mrc.Int16_BE(0x08) # must be zero, also observed to be 1
    minorVersion             = mrc.Int16_BE(0x0A)
    sceneTrackID             = mrc.Int32_BE(0x0C)
    loResSceneTrackID        = mrc.Int32_BE(0x10)
    reserved3                = mrc.Bytes(0x14, length = 4 * 6)
    hotSpotTrackID           = mrc.Int32_BE(0x2C)
    reserved4                = mrc.Bytes(0x30, length = 4 * 9)
    hPanStart                = FixedFractionField(0x54)
    hPanEnd                  = FixedFractionField(0x58)
    vPanTop                  = FixedFractionField(0x5C)
    vPanBottom               = FixedFractionField(0x60)
    minimumZoom              = FixedFractionField(0x64)
    maximumZoom              = FixedFractionField(0x68)

    # info for the highest res version of scene track
    sceneSizeX               = mrc.UInt32_BE(0x6C)
    sceneSizeY               = mrc.UInt32_BE(0x70)
    numFrames                = mrc.UInt32_BE(0x74)
    reserved5                = mrc.Int16_BE(0x78)
    sceneNumFramesX          = mrc.Int16_BE(0x7A)
    sceneNumFramesY          = mrc.Int16_BE(0x7C)
    sceneColorDepth          = mrc.Int16_BE(0x7E)

    # info for the highest rest version of hotSpot track
    hotSpotSizeX             = mrc.Int32_BE(0x80) # pixel width of the hot spot panorama
    hotSpotSizeY             = mrc.Int32_BE(0x84) # pixel height of the hot spot panorama
    reserved6                = mrc.Int16_BE(0x88)
    hotSpotNumFramesX        = mrc.Int16_BE(0x8A) # diced frames wide
    hotSpotNumFramesY        = mrc.Int16_BE(0x8C) # dices frame high
    hotSpotColorDepth        = mrc.Int16_BE(0x8E) # must be 8


class SampleDescriptionTable(ContainerAtom):
    CHUNK_MAP = mrcdict()
    CHUNK_MAP.base_class = VideoSampleDescriptionTableEntry
    MAPPING: dict[bytes, type[PanoSampleDescriptionTableEntry] | type[VideoSampleDescriptionTableEntry]] = {
        b"pano": PanoSampleDescriptionTableEntry
    }
    # set defaults for known image compression formats
    image_compression_formats = [b"cvid", b"rpza", b"smc ", b"rle ", b"cvid"]
    for codec in image_compression_formats:
        MAPPING[codec] = VideoSampleDescriptionTableEntry

    CHUNK_MAP.update(MAPPING)

    data_format = mrc.UInt32_BE(0x04)


class stsdAtom(mrc.Block):
    """
    Sample description

    ## todo: check if data_format is in sample_description table and contains qtvr
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    number_of_entries        = mrc.UInt32_BE(0x04)
    sample_description_table = mrc.BlockField(SampleDescriptionTable, 0x08, count=mrc.Ref("number_of_entries"))


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
    field_of_view            = FixedFractionField(0x10)
    startHPan                = FixedFractionField(0x14) # start horizontal pan angle in degrees
    endHPan                  = FixedFractionField(0x18) # end horizontal pan angle in degrees
    endVPan                  = FixedFractionField(0x1C) # end vertical pan angle in degrees
    startVPan                = FixedFractionField(0x20) # start vertical pan angle in degrees
    initialHPan              = FixedFractionField(0x24) # initial horizontal pan angle in degrees (poster view)
    initialVPan              = FixedFractionField(0x28) # initial vertical pan angle in degrees (poster view)
    reserved2                = mrc.UInt32_BE(0x2C) # Zro


class gminAtom(mrc.Block):
    """
    Base Media Info Atom
    """
    version                  = mrc.UInt8(0x00)
    flags                    = mrc.Bytes(0x01, length=3)
    graphics_mode            = mrc.UInt16_BE(0x04)
    opcolor                  = mrc.Bytes(0x06, length=6)
    balance                  = mrc.UInt16_BE(0x0C)
    reserved                 = mrc.Bytes(0x0E, length=2)


class PanoMediaInfoIDTable(mrc.Block):
    nodeID                   = mrc.UInt32_BE(0x00)
    time                     = mrc.UInt32_BE(0x04)


class pInfAtom(mrc.Block):
    """
    PanoMediaInfo
    """
    name                     = mrc.Bytes(0x00, length=32)
    defNodeID                = mrc.UInt32_BE(0x20)
    defZoom                  = FixedFractionField(0x24)
    reserved                 = mrc.UInt32_BE(0x28)
    pad                      = mrc.Int16_BE(0x2C)
    number_of_entries        = mrc.Int16_BE(0x2E)
    IDTable                  = mrc.BlockField(PanoMediaInfoIDTable, 0x30, count=mrc.Ref("number_of_entries"))


class STpnAtom(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"pInf": pInfAtom
    }
    CHUNK_MAP.update(MAPPING)


class gmhdAtom(ContainerAtom):
    """
    base Media inforation HeaDer

    Indicates that this media information atom pertains to a base media
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {b"gmin": gminAtom,
               b"STpn": STpnAtom}

    CHUNK_MAP.update(MAPPING)

# fmt: on


class dinfAtom(ContainerAtom):
    """
    DataINFormation
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"dref": drefAtom,
    }
    CHUNK_MAP.update(MAPPING)


class stblAtom(ContainerAtom):
    """
    Sample TaBLE
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"stco": stcoAtom,
        b"stsc": stscAtom,
        b"stsd": stsdAtom,
        b"stts": sttsAtom,
        b"stsz": stszAtom,
        b"stss": stssAtom,
    }

    CHUNK_MAP.update(MAPPING)


class minfAtom(ContainerAtom):
    """
    MedINFormation

    Store handler-specific information for a track's media data.
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"hdlr": hdlrAtom,
        b"dinf": dinfAtom,
        b"stbl": stblAtom,
        b"smhd": smhdAtom,
        b"vmhd": vmhdAtom,
        b"gmhd": gmhdAtom,
    }
    CHUNK_MAP.update(MAPPING)


class edtsAtom(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {b"elst": elstAtom}
    CHUNK_MAP.update(MAPPING)


class mdiaAtom(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"mdhd": mdhdAtom,
        b"hdlr": hdlrAtom,
        b"minf": minfAtom,
    }
    CHUNK_MAP.update(MAPPING)


class trakAtom(ContainerAtom):
    """
    Track Atom

    Defines a single track of a movie.
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"mdia": mdiaAtom,
        b"tkhd": tkhdAtom,
        b"edts": edtsAtom,
    }
    CHUNK_MAP.update(MAPPING)


class ctypAtom(mrc.Block):
    """
    Controller TYPe
    """

    id = mrc.Bytes(0x00, length=4)

    @property
    def repr(self):
        _id = self.id.decode()
        return f"id={_id}"


class WLOCAtom(mrc.Block):
    """
    Window LOCation
    """

    x = mrc.UInt16_BE(0x00)
    y = mrc.UInt16_BE(0x02)


class udtaAtom(ContainerAtom):
    """
    User DaTA Atom
    """

    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"ctyp": ctypAtom,
        b"WLOC": WLOCAtom,
        b"NAVG": NAVGAtom,
    }
    CHUNK_MAP.update(MAPPING)

    atoms = mrc.ChunkField(  # pyright: ignore[reportAssignmentType]
        mrc.Ref("CHUNK_MAP"),  # pyright: ignore[reportArgumentType]
        0x00,
        id_size=4,
        length_field=mrc.UInt32_BE,
        default_klass=GobbleAtom,
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
        b"mvhd": mvhdAtom,
        b"trak": trakAtom,
        b"udta": udtaAtom,
    }
    CHUNK_MAP.update(MAPPING)


class QuickTime(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"mdat": mdatAtom,
        b"moov": moovAtom,
        b"free": freeAtom,
    }
    CHUNK_MAP.update(MAPPING)


T = TypeVar("T", bound=mrc.Block)


def get_atoms(atom: mrc.Block, atom_kls: type[T]) -> list[T]:
    atoms: list[T] = []
    if isinstance(atom, atom_kls):
        atoms.append(atom)
    if isinstance(atom, ContainerAtom):
        for chunk in atom.atoms:
            atoms.extend(get_atoms(chunk.obj, atom_kls))
    return atoms


def get_atom(atom: mrc.Block, atom_kls: type[T]) -> T | None:
    atoms = get_atoms(atom, atom_kls)
    assert len(atoms) <= 1
    if atoms:
        return atoms[0]
    return None


def get_atom_assert(atom: mrc.Block, atom_kls: type[T]) -> T:
    ret_val = get_atom(atom, atom_kls)
    assert ret_val
    return ret_val


class QTVRType(IntEnum):
    PANORAMA = auto()
    OBJECT = auto()
    V2 = auto()


def is_qtvr(atom: mrc.Block) -> QTVRType | None:
    ctyp = get_atom(atom, ctypAtom)
    if ctyp is None:
        return None
    controller_id = ctyp.id
    if controller_id == b"stna":
        return QTVRType.OBJECT
    if controller_id in (b"stpn", b"STpn"):
        return QTVRType.PANORAMA
    if controller_id == b"qtvr":
        return QTVRType.V2
    return None
