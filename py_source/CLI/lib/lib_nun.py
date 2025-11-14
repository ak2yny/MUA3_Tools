# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# native
from dataclasses import dataclass
from struct import iter_unpack, Struct, unpack_from

#local
from .lib_gust import E, GResourceHeader # incl. endian config

# =================================================================
# NUN header
# =================================================================

# WIP: Headers are not saved. Do we need them to save files?

# III_STRUCT
@dataclass
class NunHeader:
    magic: int
    chunkSize: int
    entryCount: int

# =================================================================
# Base Class
# =================================================================

NUN_INFLUENCE_STRUCT = Struct('4i2f')

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
        self.controlPoints = [x for x in iter_unpack(E+'4f', data[pos:cpe])]
        ie = cpe + NUN_INFLUENCE_STRUCT.size * cpc
        self.influences = [NunInfluence(*x) for x in iter_unpack(E+NUN_INFLUENCE_STRUCT.format, data[cpe:ie])]
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
class NUNO(GResourceHeader):
    chunkCount: int
    Nuno1: list[NUNO1]
    Nuno2: list[NUNO2]
    Nuno3n5: list[NUNO3|NUNO5] # share layer

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nuno1 = self.Nuno2 = self.Nuno3n5 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NunHeader(*unpack_from(E+'3I', data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            match chunk.magic:
                case 0x00030001:
                    for _ in range(chunk.entryCount):
                        self.Nuno1.append(NUNO1(data, pos, self.chunkVersion))
                        pos += self.Nuno1[-1].entrySize
                case 0x00030002:
                    for _ in range(chunk.entryCount):
                        self.Nuno2.append(NUNO2(data, pos))
                        pos += self.Nuno2[-1].entrySize
                case 0x00030003:
                    for _ in range(chunk.entryCount):
                        self.Nuno3n5.append(NUNO3(data, pos, self.chunkVersion))
                        pos += self.Nuno3n5[-1].entrySize
                # case 0x00030004: pass
                case 0x00030005:
                    entryIDToNunoID, nunoIDToSubsetMap = {}, {} # the parent logic can probably be improved
                    if self.chunkVersion >= 0x30303335: pos += 4 # or for all nuno versions?
                    for i in range(chunk.entryCount):
                        nuno = NUNO5(data, pos, entryIDToNunoID)
                        if nuno.entryID not in entryIDToNunoID: entryIDToNunoID[nuno.entryID] = i
                        self.Nuno3n5.append(nuno)
                        pos += nuno.entrySize
                    for nuno in self.Nuno3n5:
                        # WIP: https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/G1M/NUNO.h#L353
                        if nuno.parentSetID > -1:
                            if nuno.parentSetID not in nunoIDToSubsetMap:
                                nunoIDToSubsetMap[nuno.parentSetID] = {
                                    (sum(cp[:3]) + cp[0]): n for n, cp in enumerate(self.Nuno3n5[nuno.parentSetID].controlPoints)
                                }
                            tempMap = nunoIDToSubsetMap[nuno.parentSetID]
                            for j, cp in enumerate(nuno.controlPoints):
                                key = sum(cp[:3]) + cp[0]
                                if key in tempMap:
                                    nuno.influences[j].P1 = tempMap[key] # replace P1??
                                else:
                                    raise ValueError(f'NUNO5 {nuno.entryID}: {key} (new P1 influence) not found in item {nuno.parentSetID}')
            pos = end

# =================================================================
# NUNS Structures
# =================================================================

NUNS_INFLUENCE_STRUCT = Struct('4i4f')

@dataclass
class NunsInfluence(NunInfluence): # P7+8 always little endian (probably a mistake)? Note: eArmada8 defined them as i
    P7: float
    P8: float

@dataclass
class NUNS1(NUN):
    def __init__(self, data: bytes, pos: int):
        self.parentBoneID, controlPointCount = unpack_from(E+'2I', data, pos)
        pos += 8 + 0xB8 # what is here?
        pos = self.readLists(data, pos, controlPointCount)
        pos = data.index((b'BLW0' if E == '>' else b'0WLB'), pos) # seems to depend on endian (?)
        # if step is important: while data[pos:pos + 4] != (b'BLW0' if E == '>' else b'0WLB'): pos += 4
        self.entrySize = pos + 20 + unpack_from('< I', data, pos + 4)[0] # what is BLW0? | always little endian or mistake?

    def readLists(self, data: bytes, pos: int, cpc: int):
        cpe = pos + 16 * cpc
        self.controlPoints = [x for x in iter_unpack(E+'4f', data[pos:cpe])]
        ie = cpe + NUNS_INFLUENCE_STRUCT.size * cpc
        self.influences = [NunsInfluence(*x) for x in iter_unpack(E+NUNS_INFLUENCE_STRUCT.format, data[cpe:ie])]
        return ie

@dataclass
class NUNS(GResourceHeader):
    chunkCount: int
    Nuns1: list[NUNS1]

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nuns1 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NunHeader(*unpack_from(E+'3I', data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            if chunk.magic == 0x00060001: # or chunk.magic == 0x00050001 ?
                for _ in chunk.entryCount:
                    self.Nuns1.append(NUNS1(data, pos))
                    pos += self.Nuns1[-1].entrySize
            else:
                raise ValueError(f'Unsupported NUNS version {chunk.magic}')
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
    Nunv1: list[NUNV1]

    def __init__(self, data: bytes, pos: int):
        self.magic, self.chunkVersion, self.chunkSize, self.chunkCount = unpack_from(E+'4I', data, pos)
        self.Nunv1 = []
        pos += 16
        for _ in range(self.chunkCount):
            chunk = NunHeader(*unpack_from(E+'3I', data, pos))
            end = pos + chunk.chunkSize
            pos += 12
            if chunk.magic == 0x00050001: # or chunk.magic == 0x00050001 ?
                for _ in chunk.entryCount:
                    self.Nunv1.append(NUNV1(data, pos))
                    pos += self.Nunv1[-1].entrySize
            else:
                raise ValueError(f'Unsupported NUNV version {chunk.magic}')
            self.Nunv1.append(chunk)
            pos = end


# =================================================================
# Nun Functions
# =================================================================
