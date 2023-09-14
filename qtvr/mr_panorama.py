from mrcrowbar import models as mrc
from mrcrowbar.utils import from_uint32_be as FourCC
from mrcrowbar.utils import to_uint32_be as FourCCB

from pathlib import Path

from .mr_quicktime import (
    ContainerAtom,
    AppleFloatField,
    get_atoms,
    trakAtom,
    gmhdAtom,
    get_atom,
    stszAtom,
    stcoAtom,
    mrcdict,
)

class HotSpot(mrc.Block):
    hotSpotID           = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    type                = mrc.UInt32_BE(0x04) # the hotspot type( e.g. link, navg)
    typeData            = mrc.UInt32_BE(0x08) # for link and navg, the ID in the link and navg table
    
    # canonical view for this hot spot
    viewHPan            = AppleFloatField(0x0C)
    viewVPan            = AppleFloatField(0x10)
    viewZoom            = AppleFloatField(0x14)

    # HotspotRect
    # todo: how to read in one go
    rect1               = mrc.UInt16_BE(0x18)
    rect2               = mrc.UInt16_BE(0x1A)
    rect3               = mrc.UInt16_BE(0x1C)
    rect4               = mrc.UInt16_BE(0x1E)

    mouseOverCursorID   = mrc.Int32_BE(0x20)
    mouseDownCursorID   = mrc.Int32_BE(0x24)
    mouseUpCursorID     = mrc.Int32_BE(0x28)
    reserved2           = mrc.Int32_BE(0x2C)
    nameStrOffset       = mrc.Int32_BE(0x30)
    commentStrOffset    = mrc.Int32_BE(0x34)


class HotSpotTableAtom(mrc.Block):
    pad                 = mrc.Bytes(0x00, length=2) # must be zero
    numHotSpots         = mrc.Int16_BE(0x02)
    HotSpots            = mrc.BlockField(HotSpot, 0x04, count=mrc.Ref("numHotSpots"))


class StringTableAtom(mrc.Block):
    # concatenated pascal strings
    bunchOfStrings      = mrc.Bytes()

class PanoSampleHeader(mrc.Block):
    nodeID              = mrc.UInt32_BE(0x00)
    
    # default values when displaying this node
    defHPan             = AppleFloatField(0x04)
    defVPan             = AppleFloatField(0x08)
    defZoom             = AppleFloatField(0x0C)

    # constrains for this node; zero for default
    minHpan             = AppleFloatField(0x10)
    minVPan             = AppleFloatField(0x14)
    minZoom             = AppleFloatField(0x18)
    maxHPan             = AppleFloatField(0x1C)
    maxVPan             = AppleFloatField(0x20)
    maxZoom             = AppleFloatField(0x24)
    
    reserved1           = mrc.Int32_BE(0x28)
    reserved2           = mrc.Int32_BE(0x2C)
    nameStrOffset       = mrc.Int32_BE(0x30)
    commentStrOffset    = mrc.Int32_BE(0x34)

class PanoLink(mrc.Block):
    LinkID              = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    reserved2           = mrc.UInt32_BE(0x04) # must be zero
    reserved3           = mrc.UInt32_BE(0x08) # for link and navg, the ID in the link and navg table

    toNodeID            = mrc.UInt32_BE(0x0C)

    reserved4           = mrc.Bytes(0x10, length = 4 * 3)
    
    # values to set at the destination node
    toHPan              = AppleFloatField(0x1C)
    toVPan              = AppleFloatField(0x20)
    toZoom              = AppleFloatField(0x24)

    reserved5           = mrc.Int32_BE(0x28)
    reserved6           = mrc.Int32_BE(0x2C)

    nameStrOffset       = mrc.Int32_BE(0x30)
    commentStrOffset    = mrc.Int32_BE(0x34)

class LinkTableAtom(mrc.Block):
    pad                 = mrc.Bytes(0x00, length=2) # must be zero
    numLinks            = mrc.Int16_BE(0x02)
    PanoLink            = mrc.BlockField(PanoLink, 0x04, count=mrc.Ref("numLinks"))

class NavgObject(mrc.Block):
    objID               = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    reserved2           = mrc.UInt32_BE(0x04) # must be zero
    navgPan             = mrc.UInt32_BE(0x08)           
    navgZoom            = mrc.UInt32_BE(0x0C)

    # zoomRect
    # starting rect for zoom out transition
    # todo: how to read in one go
    rect1               = mrc.UInt16_BE(0x10)
    rect2               = mrc.UInt16_BE(0x12)
    rect3               = mrc.UInt16_BE(0x14)
    rect4               = mrc.UInt16_BE(0x16)

    reserved3           = mrc.Int32_BE(0x18)
    
    # values to set at the destination node
    nameStrOffset       = mrc.Int32_BE(0x1C)
    commentStrOffset    = mrc.Int32_BE(0x20)


class NavgTableAtom(mrc.Block):
    pad                 = mrc.Bytes(0x00, length=2) # must be zero
    numObjects          = mrc.Int16_BE(0x02)
    NavgObject          = mrc.BlockField(PanoLink, 0x04, count=mrc.Ref("numObjects"))

class PanoramaTrackSample(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        FourCC(b"pHdr"): PanoSampleHeader,
        FourCC(b"pHot"): HotSpotTableAtom,
        FourCC(b"strT"): StringTableAtom,
        FourCC(b"pLnk"): LinkTableAtom,
    }
    CHUNK_MAP.update(MAPPING)


def get_pano_track(tracks: list[trakAtom]) -> trakAtom | None:
    for track in tracks:
        if get_atom(track, gmhdAtom):
            return track
    return None


def parse_panorama_track_samples(qt: mrc.Block, filename: Path) -> list[PanoramaTrackSample]:
    tracks = get_atoms(qt, trakAtom)
    panotrack = get_pano_track(tracks)
    if not panotrack:
        print("no panoramic track")
        return None

    stsz_atom = get_atom(panotrack, stszAtom)
    sizes = [i.size for i in stsz_atom.obj.sample_size_table]
    stco_atom = get_atom(panotrack, stcoAtom)
    offsets = [i.pointer for i in stco_atom.obj.chunk_offset_table]

    track_sampes = []
    f = open(filename, "rb")
    for offset, size in zip(offsets, sizes):
        f.seek(offset)
        data = f.read(size)
        track_sampes.append(PanoramaTrackSample(data))
    
    f.close()
    return track_sampes
