# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# native
from dataclasses import dataclass, field
from struct import calcsize, iter_unpack, unpack_from

#local
from lib.lib_gust import * # incl. endian config

# =================================================================
# NUN header
# =================================================================

# III_STRUCT
@dataclass
class NunHeader:
    magic: int
    chunkSize: int
    entryCount: int

# =================================================================
# Base Class
# =================================================================

NUN_INFLUENCE_STRUCT = '4i2f'
NI_SZ = calcsize(NUN_INFLUENCE_STRUCT)

@dataclass
class NunInfluence:
    P1: int
    P2: int
    P3: int
    P4: int
    P5: float
    P6: float

@dataclass
class NUN:
    parentBoneID: int
    entrySize: int
    controlPoints: list[tuple[float]]
    influences: list[NunInfluence]

# =================================================================
# NUNO Structures
# =================================================================

@dataclass
class NUNO1(NUN):
    def __init__(self, data: bytes, pos: int, version: int):
        # For parentBoneID (parent bone ID), could be E+'2H' or '< 2H', and use first if little, otherwise second, but unlikely
        self.parentBoneID, controlPointCount, unknownSectionCount, *skip = unpack_from(E+'6I', data, pos)
        pos += 24 + (0x5C if version >= 0x30303235 else 0x4C if version > 0x30303233 else 0x3C) # what is here?
        self.entrySize = self.readLists(data, pos, controlPointCount) + 48 * unknownSectionCount + 4 * sum(skip)

    def readLists(self, data: bytes, pos: int, cpc: int):
        cpe = pos + 16 * cpc
        self.controlPoints = [x for x in iter_unpack('4f', data[pos:cpe])]
        ie = cpe + NI_SZ * cpc
        self.influences = [NunInfluence(*x) for x in iter_unpack(NUN_INFLUENCE_STRUCT, data[cpe:ie])]
        return ie

@dataclass
class NUNO2(NUN):
    # no influences
    def __init__(self, data: bytes, pos: int):
        self.parentBoneID, *controlPoint = unpack_from(E+'I104x3f', data, pos)
        self.controlPoints.append(controlPoint)
        self.entrySize = 128 # hardcoded

@dataclass
class NUNO3(NUNO1):
    # parentSetID: int Debugging only, in case a file has mixed versions
    def __init__(self, data: bytes, pos: int, version: int):
        self.parentBoneID, controlPointCount, unknownSectionCount, *skip = unpack_from(E+'4I4x3I', data, pos)
        pos += 40 + (unpack_from(E+'I', data, pos + 40) if version >= 0x30303330 else 0xB0 if version >= 0x30303235 else 0xA0) # what is here?, WIP: is it 0x30303332 instead of 0x30303330?
        self.entrySize = self.readLists(data, pos, controlPointCount) + 48 * unknownSectionCount + 4 * skip[0] + 8 * skip[1] + 12 * skip[2] + 8 * skip[3]

@dataclass
class NUNO5(NUN):
    entryID: int
    parentSetID: int

    def __init__(self, data: bytes, pos: int, entryIDToNunoID: dict):
        # WIP: https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/G1M/NUNO.h#L200
        self.parentBoneID, lodCount, self.entryID, cond = unpack_from(E+'I4xI8x2H12x', data, pos) # Are the two shorts (2H) always little endian?
        self.parentSetID = entryIDToNunoID[self.entryID] if cond & 0x7FF and self.entryID in entryIDToNunoID else -1

        for i in range(lodCount):
            controlPointCount, flags, *skip, has_unk, unk_sz, unk_count = unpack_from(E+'14I', data, pos + 36)
            pos += 92 if has_unk else 84
            pos += unpack_from(E+'I', data, pos) # skipping?

            end = pos + 44 * controlPointCount
            if i == 0: # only LOD0 is put into lists
                for u in iter_unpack(E+'3f12x4if', data[pos:end]):
                    self.controlPoints.append(u[:3] + (1.0,)) # according to eArmada8
                    self.influences.append(NunInfluence(*u[3:], 0.0)) # Note: P5 and P6 are incorrect, but not used

            # Skipping the other parts, that define physics parameters and other info
            # (order: flags 0+1, skip0-7, flags 2, skip 8, unk)
            pos = end + skip[0] * 4 + skip[1] * 12 + skip[2] * 16 + skip[3] * 12 + skip[4] * 8 + skip[5] * 0x30 + skip[6] * 0x48 + skip[7] * 0x20
            if flags & 1<<0: pos += 32 * controlPointCount
            if flags & 1<<1: pos += 24 * controlPointCount
            if flags & 1<<2: pos += 4 * controlPointCount
            for _ in range(skip[8]):
                pos += unpack_from(E+'I', data, pos)[0] * 4 + 16 # Or always little endian?
            if has_unk: pos += unk_sz * unk_count

        self.entrySize = pos

@dataclass
class NUN_chunk(NunHeader):
    entries: list = field(default_factory=list) # WIP: Instead of entries, could possibly access NUNO1 in Nuno1, etc. directly

@dataclass
class NUNO(GResourceHeader):
    chunkCount: int
    Nuno1: list[NUNO1]
    Nuno2: list[NUNO2]
    Nuno3n5: list[NUNO3|NUNO5] # share layer 30000

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nuno1 = self.Nuno2 = self.Nuno3n5 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NunHeader(*unpack_from(E+III_STRUCT, data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            if chunk.magic == 0x00030005:
                entryIDToNunoID = nunoIDToSubsetMap = {} # the parent logic can probably be improved
                if self.chunkVersion >= 0x30303335: pos += 4 # or for all nuno magics?
            for i in range(chunk.entryCount):
                nuno = NUNO1(data, pos, self.chunkVersion) if chunk.magic == 0x00030001 else \
                       NUNO2(data, pos) if chunk.magic == 0x00030002 else \
                       NUNO3(data, pos, self.chunkVersion) if chunk.magic == 0x00030003 else \
                       NUNO5(data, pos, entryIDToNunoID) if chunk.magic == 0x00030005 else \
                       None
                if not nuno: continue #skip 0x00030004
                if chunk.magic == 0x00030005:
                    # WIP: https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/G1M/NUNO.h#L353
                    if nuno.entryID not in entryIDToNunoID: entryIDToNunoID[nuno.entryID] = i
                    if nuno.parentSetID > -1:
                        if nuno.parentSetID not in nunoIDToSubsetMap:
                            nunoIDToSubsetMap[nuno.parentSetID] = {
                                (cp[0] * 2 + cp[1] + cp[2]): n for n, cp in enumerate(chunk.entries[nuno.parentSetID].controlPoints)
                            }
                        tempMap = nunoIDToSubsetMap[nuno.parentSetID]
                        for i, cp in enumerate(nuno.controlPoints):
                            key = (cp[0] * 2 + cp[1] + cp[2])
                            if key in tempMap:
                                nuno.influences[i].P1 = tempMap[key] # replace P1??
                            else:
                                raise ValueError(f'NUNO5 {nuno.entryID}: {key} (new P1 influence) not found in item {nuno.parentSetID}')
                # Note: It seems like the G1MGMesh.externalID refers to stacked NUNOs but types 3 and 5 seem to share it
                match chunk.magic:
                    case 0x00030001:
                        self.Nuno1.append(chunk)
                    case 0x00030002:
                        self.Nuno2.append(chunk)
                    case 0x00030003:
                        self.Nuno3n5.append(chunk)
                    case 0x00030005:
                        self.Nuno3n5.append(chunk)
                pos += nuno.entrySize
            pos = end

# =================================================================
# NUNS Structures
# =================================================================

NUNS_INFLUENCE_STRUCT = '4i4f'
NSI_SZ = calcsize(NUN_INFLUENCE_STRUCT)

@dataclass
class NunsInfluence(NunInfluence): # P7+8 always little endian? Note: eArmada8 defined them as i
    P7: float
    P8: float

@dataclass
class NUNS1(NUN):
    def __init__(self, data: bytes, pos: int):
        self.parentBoneID, controlPointCount = unpack_from(E+'2I', data, pos)
        pos += 8 + 0xB8 # what is here?
        pos = self.readLists(data, pos, controlPointCount)
        while (data[pos:pos + 4] if E == '>' else data[pos:pos + 4][::-1]) != b'BLW0': pos += 4
        self.entrySize = pos + 20 + unpack_from('< I', data, pos + 4)[0] # what is BLW0?

    def readLists(self, data: bytes, pos: int, cpc: int):
        cpe = pos + 16 * cpc
        self.controlPoints = [x for x in iter_unpack('4f', data[pos:cpe])]
        ie = cpe + NSI_SZ * cpc
        self.influences = [NunsInfluence(*x) for x in iter_unpack(NUNS_INFLUENCE_STRUCT, data[cpe:ie])]
        return ie

@dataclass
class NUNS(GResourceHeader):
    chunkCount: int
    Nuns1: list[NUN_chunk]

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nuns1 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NUN_chunk(*unpack_from(E+III_STRUCT, data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            if chunk.magic == 0x00060001: # or chunk.magic == 0x00050001 ?
                for _ in chunk.entryCount:
                    chunk.entries.append(NUNS1(data, pos))
                    pos += chunk.entries[-1].entrySize
            else:
                chunk.entries.append({'Error': 'unsupported NUNS'})
            self.Nuns1.append(chunk)
            pos = end

# =================================================================
# NUNV Structures
# =================================================================

@dataclass
class NUNV1(NUNO1):
    def __init__(self, data: bytes, pos: int, version: int):
        self.parentBoneID, controlPointCount, unknownSectionCount, skip = unpack_from(E+'4I', data, pos)
        pos += 16 + (0x64 if version >= 0x30303131 else 0x54) # what is here?
        self.entrySize = self.readLists(data, pos, controlPointCount) + 48 * unknownSectionCount + 4 * skip

@dataclass
class NUNV(GResourceHeader):
    chunkCount: int
    Nunv1: list[NUN_chunk]

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nunv1 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NUN_chunk(*unpack_from(E+III_STRUCT, data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            if chunk.magic == 0x00050001: # or chunk.magic == 0x00050001 ?
                for _ in chunk.entryCount:
                    chunk.entries.append(NUNV1(data, pos))
                    pos += chunk.entries[-1].entrySize
            else:
                chunk.entries.append({'Error': 'unsupported NUNV'})
            self.Nunv1.append(chunk)
            pos = end


# =================================================================
# Nun Functions
# =================================================================
