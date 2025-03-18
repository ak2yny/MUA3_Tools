# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# native
from dataclasses import dataclass, field, InitVar
from struct import iter_unpack, unpack, unpack_from
from math import cos, sin, sqrt

# local
from .lib_gust import E # endian config


# =================================================================
# Animation headers
# =================================================================

G1A_HEAD_STRUCT = '4xI4xH2xfI24x2H' # What's in the skipped section?
G2A_HEAD_STRUCT = '4xI4xf3I'

@dataclass
class G1AHeader:
    chunkVersion: int
    animationType: int # not sure
    duration: float # in seconds
    dataSectionOffset: int    
    boneInfoCount: int
    boneMaxID: int
    def __post_init__(self):
        self.dataSectionOffset *= 16

@dataclass
class G2AHeader:
    version: int
    framerate: float
    _packedInfo: InitVar[int]
    animationLength: int = field(init=False)
    boneInfoSectionSize: int = field(init=False)
    timingSectionSize: int
    entryCount: int
    boneInfoCount: int = field(init=False)

    def __post_init__(self, _packedInfo):
        # WIP: The packed info was read endian specific as uint32 (would probably have to revert endian)
        if E == '<':
            self.animationLength = _packedInfo & 0x3FFF
            self.boneInfoSectionSize = (_packedInfo >> 18) & 0x3FFC
        else:
            self.animationLength = _packedInfo >> 18
            self.boneInfoSectionSize = (_packedInfo & 0x3FFF) << 2
        self.boneInfoCount = self.boneInfoSectionSize >> 2
    @property
    def bIsG2A5(self) -> bool:
        return self.version == 0x30303530
    @property
    def bIsG2A4(self) -> bool:
        return self.version == 0x30303430

# =================================================================
# Main Animation Classes
# =================================================================

class G1A:
    # animName: str
    # joints # modelBone_t from Noesis
    # jointCount: int
    # pointersToFree: list # of type noeKeyFramedAnim_t from Noesis
    framerate: int
    animData: dict # noesisAnim_t from Noesis

    def __init__(self, data: bytes, globalToFinal: dict = None):
        header = G1AHeader(*unpack_from(E+G1A_HEAD_STRUCT, data))
        timeIndex = -1 if header.chunkVersion > 0x30303430 else 0
        animationData = []
        self.animData = {}
        for boneID, splineInfoOffset in iter_unpack(E+'2I', data[52:52 + 8 * header.boneInfoCount]):
            if boneID not in globalToFinal:
                continue
            # Noesis stuff:
            # kfBone = noeKeyFramedBone_t()
            # kfBone.boneIndex = globalToFinal[boneID]
            # kfBone.flags['additive'] = bAdditive (boolean from constructor)
            pos = 48 + splineInfoOffset * 16 # size hardcoded
            opcode, = unpack_from(E+'I', data, pos)

            allChan = [tuple(iter_unpack(E+'5f', data[pos + 16 * o:pos + 16 * o + 20 * kf]))
                      for kf, o in iter_unpack(E+'2I', data[pos + 4:pos + 4 + 8 * (
                          4 if opcode == 2 else
                          7 if opcode == 4 or opcode == 8 else
                          10 if opcode == 6 else 0)])] # 2 if opcode == 1: skipping?
            if len(allChan) < 3: continue
            # Rotation
            animationData += function3(allChan, 0 if opcode < 6 else 3, 4, timeIndex)
            # Translation
            if opcode == 4 or opcode == 6:
                animationData += function3(allChan, 4 if opcode == 4 else 7, 3, timeIndex)
            # Scale
            if opcode > 4:
                animationData += function3(allChan, 0, 3, timeIndex)
            # WIP: What to do with this data?
            # Something's wrong with g1a. It should be frames/time-indices for each bone
            self.animData[globalToFinal[boneID]] = animationData
            self.framerate = 30

            # Noesis stuff:
            # keyFramedBones.append(kfBone)
            # keyFramedValuesIndices.append(valueIndex)
        # for u, vi in enumerate(keyFramedValuesIndices):
            # kfBone = keyFramedBones[u]
            # if vi.rotIndex >= 0: kfBone.rotationKeys = keyFramedValues[vi.rotIndex]
            # if vi.posIndex >= 0: kfBone.translationKeys = keyFramedValues[vi.posIndex]
            # if vi.scaleIndex >= 0: kfBone.scaleKeys = keyFramedValues[vi.scaleIndex]
        # keyFramedAnim: noeKeyFramedAnim_t = ...

@dataclass
class G2A:
    # animName: str
    # joints # modelBone_t from Noesis
    # jointCount: int
    # pointersToFree: list # of type noeKeyFramedAnim_t from Noesis
    framerate: int
    animData: dict

    def __init__(self, data: bytes, globalToFinal: dict = None):
        header = G2AHeader(*unpack_from(E+G2A_HEAD_STRUCT, data))
        header_sz = 32 if header.bIsG2A5 or header.bIsG2A4 else 28 # size hardcoded?
        self.framerate = header.framerate # or self.header = G2AHeader(*unpack_from(E+G2A_HEAD_STRUCT, data))
        lastID = globalOffset = 0
        animationData = []
        self.animData = {}
        # keyFramedValues = []
        for packedInfo, in iter_unpack(E+'I', data[pos:pos + 4 * header.boneInfoCount]):
            if E == '<':
                boneID = (packedInfo >> 4) & (0xFF if header.bIsG2A5 else 0x3FF)
                splineTypeCount = packedInfo & 0xF
                boneTimingDataOffset = packedInfo >> (12 if header.bIsG2A5 else 14)
            else:
                boneID = (packedInfo >> 16) & 0xFFF
                splineTypeCount = packedInfo >> 28
                boneTimingDataOffset = (packedInfo & 0xFFFF) << 2
            if boneID < lastID: globalOffset += 1
            lastID = boneID
            boneID += globalOffset * (256 if header.bIsG2A5 else 1024)
            if boneID not in globalToFinal:
                continue # WIP: If skeleton doesn't have data, animation is not complete
            boneIndex = globalToFinal[boneID]
            self.animData[boneIndex] = {}
            # Noesis stuff:
            # kfBone = noeKeyFramedBone_t()
            # kfBone.boneIndex = boneIndex
            # kfBone.flags['additive'] = bAdditive (boolean from constructor)
            pos = header_sz + header.boneInfoSectionSize + boneTimingDataOffset
            pos -= pos % 4

            # WIP: Exception, as the function1 and 2 aren't working (yet) and its only Noesis.
            for i in range(splineTypeCount):
                opcode, kf, o = unpack_from(E+'2HI', data, pos)
                keyFrameTimings = unpack_from(f'{E} {kf}H', data, pos + 8)
                pos2 += 8 + 2 * kf
                pos2 += (4 - pos) % 4
                pos = header_sz + header.boneInfoSectionSize + header.timingSectionSize + o * 32
                quantizedData = tuple(iter_unpack(E+'4Q', data[pos:pos + 32 * kf]))
                pos = pos2
                if kf > 1 and keyFrameTimings[-1] != header.animationLength:
                    keyFrameTimings = keyFrameTimings + (header.animationLength, )
                for k in range(max(kf - 1, 1)):
                    # WIP: What to do with this data? Is this Noesis calculation of any use?
                    if opcode not in [0, 1, 2]: continue
                    kf_v = keyFrameTimings[k]
                    kf_r = 1 if kf == 1 else keyFrameTimings[k + 1] - kf_v
                    if opcode == 0:
                        # kfBone.numRotationKeys += kf_r
                        # valueIndex.rotIndex: keyFramedValueIndex += len(keyFramedValues)
                        pass
                    elif opcode == 1:
                        # kfBone.numTranslationKeys += kf_r
                        # valueIndex.posIndex: keyFramedValueIndex += len(keyFramedValues)
                        pass
                    else: # 2
                        # kfBone.numScaleKeys += kf_r
                        # valueIndex.scaleIndex: keyFramedValueIndex += len(keyFramedValues)
                        pass
                    for l in range(kf_r):
                        vec = function1(quantizedData[k], l, kf_r) # ?, to RichVec3
                        # noeKfValue.time = 0.01 if kf == 1 else (kf_v + l) / header.framerate
                        if opcode == 0:
                            quat = function2(vec)
                            # quat.Transpose()
                            # value_count = 4
                            # animationData += [q for q in quat.q]
                        else:
                            # value_count = 3
                            # animationData += [v for v in vec.v]
                            pass
                        # ...... keyFramedValues.append(noeKfValue: noeKeyFrameData_t)
                # WIP:Data needs to be parsed
                self.animData[boneIndex][i] = (keyFrameTimings, quantizedData)
            # keyFramedBones.append(kfBone)
            # keyFramedValuesIndices.append(valueIndex)
        # for u, valueIndex in enumerate(keyFramedValuesIndices): # duplicate loop?
        #   kfBone = keyFramedBones[u]
        #   if valueIndex.rotIndex >= 0: kfBone.rotationKeys = keyFramedValues[valueIndex.rotIndex]
        #   if valueIndex.posIndex >= 0: kfBone.translationKeys = keyFramedValues[valueIndex.posIndex]
        #   if valueIndex.scaleIndex >= 0: kfBone.scaleKeys = keyFramedValues[valueIndex.scaleIndex]
        # Noesis uses the noeKeyFramedAnim_t class to add information like animName, animName, numBones (len(globalToFinal)), keyFramedBones, animationData
        # as well as the noesisAnim_t class to add it to joints+jointCount with animName, flags

        


# =================================================================
# Keyframe Classes (temporary, as a placeholder for Noesis)
# =================================================================

class keyFramedValueIndex:
    rotIndex: int
    posIndex: int
    scaleIndex: int

"""
class noeKeyFramedBone_t:
    boneIndex: int
    rotationInterpolation: ?
    translationInterpolation: ?
    scaleInterpolation: ?
    translationType: tuple
    rotationType: tuple
    scaleType: tuple
    flags: dict
"""

# =================================================================
# Animation Functions
# =================================================================

def function1(quantizedData: tuple, currentTime: float, totalTime: float) -> tuple:
    """
    Convert G2A quantisized data to Vector (Noesis specific RichVec3)
    """
    # is this calculation of any use for Blender?
    time_pc = currentTime / totalTime
    f = (0, time_pc, time_pc ** 2, time_pc ** 3)
    d = unpack('4f', pack('4I', *(((x >> 0x25) & 0x7800000) + 0x32000000 for x in quantizedData))) # WIP

    # WIP: xyzw to wxyz seems to be quaternion data, partly seen in function 2.
    # Quantisized data:                11111 000  z
    #                            11 111000        y
    #                       1111100 0             x
    #                    0x11111111 11111111      quantisized
    # The extracted quantisized data must be signed, then factored (factors still unknown)
    # Note that the data is summarized, thus the order (w, x, y, z) doesn't matter
    return(
        sum((((row >> q << 0x0C & 0xFFFFF000) ^ 0x80000000) - 0x80000000) * d[i] * f[i]
            for i, row in enumerate(quantizedData))
        for q in (0x28, 0x14, 0x00)
    )
    #for i, row in enumerate((quantizedData[3], *quantizedData[:3])):

    #time_squared = time_pc ** 2
    #time_cubed = time_pc ** 3
    #row1, row2, row3, row4 = quantizedData
    #x, y, z, w = unpack('4f', pack('4I', *(((x >> 0x25) & 0x7800000) + 0x32000000 for x in quantizedData)))
    #return (
    #    # WIP: float(int()) is probably wrong
    #    float(int((row4 >> 28) & 0xFFFFF000)) * w * time_cubed +
    #    float(int((row1 >> 28) & 0xFFFFF000)) * x +
    #    float(int((row2 >> 28) & 0xFFFFF000)) * y * time_pc +
    #    float(int((row3 >> 28) & 0xFFFFF000)) * z * time_squared,
    #
    #    float(int((row4 >> 8) & 0xFFFFF000)) * w * time_cubed +
    #    float(int((row1 >> 8) & 0xFFFFF000)) * x +
    #    float(int((row2 >> 8) & 0xFFFFF000)) * y * time_pc +
    #    float(int((row3 >> 8) & 0xFFFFF000)) * z * time_squared,
    #
    #    float(int(row4 << 12)) * w * time_cubed +
    #    float(int(row1 << 12)) * x +
    #    float(int(row2 << 12)) * y * time_pc +
    #    float(int(row3 << 12)) * z * time_squared
    #)

def function2(vec: tuple[float]):
    """
    WIP: Convert from Noesis RichVec3 to RichQuat, is his calculation of any use for Blender?
    If so, the math can be simplified with numpy.
    """
    angle = sqrt(sum(v ** 2 for v in vec))
    f = sin(angle * 0.5) / angle if angle > 0.000011920929 else 0.5
    return (*(v * f for v in vec), cos(angle * 0.5))
    #if angle > 0.000011920929:
    #    f = sin(angle * 0.5) / angle
    #    quat.q[0] = vec.v[0] * f
    #    quat.q[1] = vec.v[1] * f
    #    quat.q[2] = vec.v[2] * f
    #else:
    #    quat.q[0] = vec.v[0] * 0.5
    #    quat.q[1] = vec.v[1] * 0.5
    #    quat.q[2] = vec.v[2] * 0.5
    #quat.q[3] = cos(angle * 0.5)
    #return quat

def function3(chan: list, index: int, componentCount: int, t_indx: int):
    """
    Takes a lists of G1A data for a channel (rot, transl., scale).
    Creates a list of used key frames and for each, yields the channel data.
    (Animation caps at the last used keyframe.)
    """
    allTimes = set(x[t_indx] for x in sum(chan[index:index + componentCount]))
    allTimes.add(0.0)
    allTimes = sorted(allTimes) # add would usually sort the set, but it's not guaranteed
    for t in allTimes:
        values = []
        for u in range(index, index + componentCount):
            i = len(chan[u]) - 1
            for v, t1 in enumerate(chan[u]):
                if t < t1[t_indx]:
                    i = v
                    break
            # WIP: Is this calculation Noesis specific? (What's tratio?)
            t0 = chan[u][max(i - 1, 0)][t_indx]
            tratio = (t - t0) / (chan[u][i][t_indx] - t0)
            values.append(chan[u][i][t_indx + 1] * pow(tratio, 3) + chan[u][i][t_indx + 2] * pow(tratio, 2) + chan[u][i][t_indx + 3] * tratio + chan[u][i][t_indx + 4])
        if componentCount == 4: # rotation
            pass
            # WIP: values = Quaternion(values).GetTranspose() > should be a tuple or list
        yield values
        # Noesis specific:
        # kfBone: noeKeyFramedBone_t .numRotationKeys or .numTranslationKeys or .numScaleKeys = len(allTimes)
        # noeKfValue.time = t
        # noeKfValue.dataIndex = current len('yielded') - componentCount
        # valueIndex: keyFramedValueIndex .rotIndex or .posIndex or .scaleIndex = len(keyFramedValues)
        # keyFramedValues: list[noeKeyFrameData_t] append noeKfValue
