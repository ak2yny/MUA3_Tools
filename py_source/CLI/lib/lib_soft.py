# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword, Raytwo and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).
#
# WIP:
# https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/G1M/SOFT.h#L3C23
# https://github.com/three-houses-research-team/010-binary-templates/blob/master/Model%20related%20formats/G1M/SOFT.bt
# https://github.com/DarkStarSword/3d-fixes/blob/master/decode_doa6_soft.py

# native
from dataclasses import dataclass
from struct import Struct, unpack, unpack_from

#local
from .lib_gust import E # incl. endian config
from .lib_nun import NunHeader

# =================================================================
# SOFT header
# =================================================================

SOFT_NODEENTRYHEADER_STRUCT = Struct('13I')

@dataclass
class SoftNodeEntryHeader:
	ID: int
	nodeCount: int
	z2: int
	z3: int
	u4: int
	len2: int
	len3: int
	parentID: int
	u6: int
	u7: int
	z8: int
	o9: int
	len4: int

# =================================================================
# Unknown Structures
# =================================================================

SOFT_NODEENTRYU_STRUCT = Struct('24f')

"""
@dataclass
class SoftNodeEntryUnk1:
    unk: tuple[float] # x24

@dataclass
class SoftNodeEntryNodeInfluence: # 'If'
    ID: int
    data: float # Influence weight?

@dataclass
class SoftNodeEntryNodeData: # '3I3f'
    unk1: int
    unk2: int
    unk3: int
    unk4: float
    unk5: float
    unk6: float
"""
# =================================================================
# SOFT Structures
# =================================================================

SOFT_NODEENTRY_STRUCT = Struct('I12sfI4sI')

@dataclass
class Soft1EntryNode:
    # WIP: Unfinished
    ID: int
    pos: tuple
    rot: int # WIP: ??
    unk: int # Always 0x43?
    b: tuple
    influenceCount: int

    def __post_init__(self):
        self.pos = unpack(E+'3f', self.pos)
        self.b = unpack(E+'4B', self.b)

@dataclass
class SOFT1:
    parentID: int
    entrySize: int
    softNodes: list[Soft1EntryNode]

    def __init__(self, data: bytes, pos: int): # , version: int
        entryHeader = SoftNodeEntryHeader(*unpack_from(E+SOFT_NODEENTRYHEADER_STRUCT.format, data, pos))
        self.parentID = entryHeader.parentID
        self.softNodes = []
        pos += SOFT_NODEENTRYHEADER_STRUCT.size + SOFT_NODEENTRYU_STRUCT.size
        for _ in range(entryHeader.nodeCount):
            entryNode = Soft1EntryNode(*unpack_from(E+SOFT_NODEENTRY_STRUCT.format, data, pos))
            self.softNodes.append(entryNode)
            pos += SOFT_NODEENTRY_STRUCT.size + (entryNode.influenceCount + 1)  * 8 + 0x18
        # WIP: Info skipped
        pos += 4 * (entryHeader.u4 + entryHeader.nodeCount + entryHeader.u6 + 3 * entryHeader.len3)
        self.entrySize = pos + unpack_from(E+'I', data, pos + 4)

@dataclass
class SOFT:
    Soft1s: list[SOFT1]

    def __init__(self, data: bytes, pos: int):
        sectionCount, = unpack_from(E+'12xI', data, pos)
        pos += 16
        self.Soft1s = []
        for _ in range(sectionCount):
            subSectionHeader = NunHeader(*unpack_from(E+'3I', data, pos))
            end = pos + subSectionHeader.chunkSize
            pos += 12
            if subSectionHeader.magic == 0x00080001:
                for _ in subSectionHeader.entryCount:
                    self.Soft1s.append(SOFT1(data, pos)) # chunkVersion is unused?
                    pos += self.Soft1s[-1].entrySize
            #elif subSectionHeader.magic == 0x00080002:
            pos = end


# =================================================================
# Class Functions
# =================================================================
