from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mrcrowbar import common
from mrcrowbar import models as mrc
from mrcrowbar.lib.platforms.director import Rect
from mrcrowbar.utils import to_uint32_be as FourCCB

from .mr_quicktime import (
    FixedFractionField,
    ContainerAtom,
    get_atom,
    get_atoms,
    gmhdAtom,
    mrcdict,
    stcoAtom,
    stszAtom,
    trakAtom,
)


class strOffsetReprBlock(mrc.Block):
    @property
    def repr(self) -> str | None:
        """Plaintext summary of the Block."""
        value_map: dict[str, Any] = {}
        if self._repr_values and isinstance(self._repr_values, list):
            value_map = {
                x: getattr(self, x) for x in self._repr_values if hasattr(self, x)
            }
        else:
            value_map = {k: v for k, v in self._field_data.items()}
        values: list[str] = []
        for name, value in value_map.items():
            if name in ("nameStrOffset", "commentStrOffset"):
                output = f"<offset={value}"
                if value != 0:
                    item = self
                    while item is not None and not isinstance(
                        item._parent, PanoramaTrackSample
                    ):
                        item = item._parent
                    try:
                        assert item and isinstance(item._parent, PanoramaTrackSample)
                        st_atom = get_atom(item._parent, StringTableAtom)
                        if st_atom:
                            output += f", str={st_atom.get_string(value)}"
                    except Exception:
                        breakpoint()
                output += ">"
            elif name == "type":
                output = FourCCB(value).decode()
            elif isinstance(value, str):
                output = f"str[{len(value)}]"
            elif common.is_bytes(value):
                output = f"bytes[{len(value)}]"
            elif isinstance(value, Sequence):
                output = f"list[{len(value)}]"
            else:
                output = str(value)
            values.append(f"{name}={output}")
        return ", ".join(values)


# fmt: off

class HotSpot(strOffsetReprBlock):
    hotSpotID           = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    type                = mrc.UInt32_BE(0x04) # the hotspot type(e.g. link, navg)
    typeData            = mrc.UInt32_BE(0x08) # for link and navg, the ID in the link and navg table

    # canonical view for this hot spot
    viewHPan            = FixedFractionField(0x0C)
    viewVPan            = FixedFractionField(0x10)
    viewZoom            = FixedFractionField(0x14)

    # HotspotRect
    rect                = mrc.BlockField(Rect, 0x18)

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

    def __repr__(self):
        ret = super().__repr__()
        if self.numHotSpots == 0:
            return ret
        items = [str(item) for item in self.HotSpots]
        return "\n".join([ret, *items])


class StringTableAtom(mrc.Block):
    """
    concatenated pascal strings

    # offsets used are +8 because they include the atom header (size and fourcc)
    """
    bunchOfStrings      = mrc.Bytes()

    def get_string(self, offset: int) -> str:
        offset -= 8
        str_start = offset + 1
        str_end = str_start + self.bunchOfStrings[offset]
        return self.bunchOfStrings[str_start: str_end].decode()


class PanoSampleHeader(strOffsetReprBlock):
    nodeID              = mrc.UInt32_BE(0x00)

    # default values when displaying this node
    defHPan             = FixedFractionField(0x04)
    defVPan             = FixedFractionField(0x08)
    defZoom             = FixedFractionField(0x0C)

    # constrains for this node; zero for default
    minHpan             = FixedFractionField(0x10)
    minVPan             = FixedFractionField(0x14)
    minZoom             = FixedFractionField(0x18)
    maxHPan             = FixedFractionField(0x1C)
    maxVPan             = FixedFractionField(0x20)
    maxZoom             = FixedFractionField(0x24)

    reserved1           = mrc.Int32_BE(0x28)
    reserved2           = mrc.Int32_BE(0x2C)
    nameStrOffset       = mrc.Int32_BE(0x30)
    commentStrOffset    = mrc.Int32_BE(0x34)


class PanoLink(strOffsetReprBlock):
    LinkID              = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    reserved2           = mrc.UInt32_BE(0x04) # must be zero
    reserved3           = mrc.UInt32_BE(0x08) # for link and navg, the ID in the link and navg table

    toNodeID            = mrc.UInt32_BE(0x0C)

    reserved4           = mrc.Bytes(0x10, length = 4 * 3)

    # values to set at the destination node
    toHPan              = FixedFractionField(0x1C)
    toVPan              = FixedFractionField(0x20)
    toZoom              = FixedFractionField(0x24)

    reserved5           = mrc.Int32_BE(0x28)
    reserved6           = mrc.Int32_BE(0x2C)

    nameStrOffset       = mrc.Int32_BE(0x30)
    commentStrOffset    = mrc.Int32_BE(0x34)


class LinkTableAtom(mrc.Block):
    pad                 = mrc.Bytes(0x00, length=2) # must be zero
    numLinks            = mrc.Int16_BE(0x02)
    PanoLink            = mrc.BlockField(PanoLink, 0x04, count=mrc.Ref("numLinks"))

    def __repr__(self):
        ret = super().__repr__()
        if self.numLinks == 0:
            return ret
        items = [str(item) for item in self.PanoLink]
        return "\n".join([ret, *items])


class NavgObject(strOffsetReprBlock):
    objID               = mrc.UInt16_BE(0x00)
    reserved1           = mrc.UInt16_BE(0x02) # must be zero
    reserved2           = mrc.UInt32_BE(0x04) # must be zero
    navgHPan            = mrc.UInt32_BE(0x08)
    navgVPan            = mrc.UInt32_BE(0x0C)
    navgZoom            = mrc.UInt32_BE(0x10)

    # zoomRect
    # starting rect for zoom out transition
    rect                = mrc.BlockField(Rect, 0x14)

    reserved3           = mrc.Int32_BE(0x1C)

    # values to set at the destination node
    nameStrOffset       = mrc.Int32_BE(0x20)
    commentStrOffset    = mrc.Int32_BE(0x24)


class NavgTableAtom(mrc.Block):
    pad                 = mrc.Bytes(0x00, length=2) # must be zero
    numObjects          = mrc.Int16_BE(0x02)
    NavgObject          = mrc.BlockField(NavgObject, 0x04, count=mrc.Ref("numObjects"))

    def __repr__(self):
        ret = super().__repr__()
        if self.numObjects == 0:
            return ret
        items = [str(item) for item in self.NavgObject]
        return "\n".join([ret, *items])

# fmt: on


class PanoramaTrackSample(ContainerAtom):
    CHUNK_MAP = mrcdict()
    MAPPING = {
        b"pHdr": PanoSampleHeader,
        b"pHot": HotSpotTableAtom,
        b"strT": StringTableAtom,
        b"pLnk": LinkTableAtom,
        b"pNav": NavgTableAtom,
    }
    CHUNK_MAP.update(MAPPING)


def get_pano_track(tracks: list[trakAtom]) -> trakAtom | None:
    for track in tracks:
        if get_atom(track, gmhdAtom):
            return track
    return None


def parse_panorama_track_samples(
    qt: mrc.Block, filename: Path
) -> list[PanoramaTrackSample]:
    tracks = get_atoms(qt, trakAtom)
    panotrack = get_pano_track(tracks)
    if not panotrack:
        print("no panoramic track")
        return []

    stsz_atom = get_atom(panotrack, stszAtom)
    assert stsz_atom is not None
    if stsz_atom.sample_size:
        sizes = [stsz_atom.sample_size]
    else:
        sizes = [i.size for i in stsz_atom.sample_size_table]

    stco_atom = get_atom(panotrack, stcoAtom)
    assert stco_atom
    offsets = [i.pointer for i in stco_atom.chunk_offset_table]

    track_sampes = []
    with open(filename, "rb") as f:
        for offset, size in zip(offsets, sizes):
            f.seek(offset)
            data = f.read(size)
            track_sampes.append(PanoramaTrackSample(data))

    return track_sampes
