# Based primarily off of:
#   -  and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# requirements
import numpy as np
from numpy import ndarray
from pyquaternion import Quaternion

# local
from lib.lib_fmtibvb import *
from lib.lib_gust import * # incl. endian config

# native
import os, copy, json
from dataclasses import InitVar, dataclass, field # astuple, 
from struct import calcsize, unpack, unpack_from


G1MGM_MATERIAL_KEYS = [None, 'COLOR', 'SHADING', 'NORMAL', None, 'DIRT']
IS_G1MS_UNORDERED = False # On recent games the skeleton is laid out such as the parent is always read before the child. Not the case in very old G1M.

# =================================================================
# G1MG headers
# =================================================================

G1MG_HEADER_STRUCT = '4sI6fI'

@dataclass
class G1MGSubSectionHeader:
    magic: int
    size: int
    count: int

@dataclass
class G1MGHeader:
    platform: bytes
    reserved: int
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    sectionCount: int

# =================================================================
# OBJD header (Maps)
# =================================================================

OBJD_HEADER_STRUCT = '4s5H2x'

@dataclass
class OBJDHeader:
	magic: str
	sectionCount: int
	section0EntryCount: int
	section1EntryCount: int
	section2EntryCount: int
	section3EntryCount: int
    # padding

# =================================================================
# Skeleton data
# =================================================================

G1MS_HEADER_STRUCT = '2I4H'
G1MS_JOINT_STRUCT = '3fI8f' # eArmada8 used i and checked for negative values (self.header.jointCount > 1 and not self.joints[0].parentID < -200000000)

@dataclass
class G1MSHeader:
    jointInfoOffset: int
    unk1: int
    jointCount: int
    jointIndicesCount: int
    layer: int # May be skeleton type too
    padding: int

@dataclass
class G1MSJoint:
    sx: float
    sy: float
    sz: float
    parentID: int # local ID
    rx: float
    ry: float
    rz: float
    rw: float
    px: float
    py: float
    pz: float
    pw: float
    abs_tm: ndarray[float, float] = field(init=False)
    def __post_init__(self):
        if self.parentID == 0xFFFFFFFF: # root bone as absolute origin; if struct is i, use parentID < 0
            self.abs_tm = Quaternion(self.rotation).transformation_matrix
            self.abs_tm[3,:3] = self.position # or even (0.0, 0.0, 0.0)
    def to_matrix(self) -> ndarray:
        mat = Quaternion(self.rotation).transformation_matrix
        mat[3] = self.px, self.py, self.pz, self.pw
        return mat # @ np.diag((self.sx, self.sy, self.sz, 1))
    @property
    def rotation(self) -> tuple:
        return self.rw, self.rx, self.ry, self.rz
    @property
    def position(self) -> tuple:
        return self.px, self.py, self.pz
    @property
    def scale(self) -> tuple:
        return self.sx, self.sy, self.sz # RichVec3

@dataclass
class G1MS:
    header: G1MSHeader
    joints: list[G1MSJoint]
    # jointLocalIndexToExtract: list[int] # WIP: could probably improve this or remove it. Would have to create before using
    localIDToGlobalID: dict[int, int] # global ID is the index of the local ID in the joint index (seems to match OID)
    globalIDToLocalID: dict[int, int] # local ID corresponds with the joints list
    bIsInternal: bool

    def __init__(self, data: bytes, pos: int, version: int):
        """
        Read G1MS section, sans Gust header (G1MS magic, version, size)
        Raises an index out of range exception if jointCount is 0 (should be 1 if skeleton is external)
        """
        shs = calcsize(G1MS_HEADER_STRUCT)
        self.header = G1MSHeader(*unpack_from(E+G1MS_HEADER_STRUCT, data, pos + 12))
        self.joints = [G1MSJoint(*unpack_from(E+G1MS_JOINT_STRUCT, data, p)) for p in range(pos + self.header.jointInfoOffset, pos + self.header.jointInfoOffset + self.header.jointCount * 48, 48)]
        if version < 0x30303332:
            # no global indices in early versions, it seems
            self.globalIDToLocalID = self.localIDToGlobalID = {i: i for i in range(self.header.jointCount)}
            self.bIsInternal = True
        else:
            self.globalIDToLocalID = self.localIDToGlobalID = {}
            for i, localID in enumerate(unpack_from(f'{E} {self.header.jointIndicesCount}H', data, pos + 12 + shs)):
                if not localID == 0xFFFF:
                    self.localIDToGlobalID[localID] = i
                    self.globalIDToLocalID[i] = localID
            self.bIsInternal = self.joints[0].parentID != 0x80000000

    # WIP: Might be useful
    def getGlobalID(self, localID: int) -> int:
        return self.localIDToGlobalID[localID ^ 0x80000000 if self.bIsInternal and localID >> 31 else \
                                      self.findLocalID(localID)]

    def findLocalID(self, localID: int) -> int:
        while localID not in self.localIDToGlobalID and localID < 100000:
            localID += 10000
        return localID

    def getJoint(self, globalID: int) -> G1MSJoint:
        return self.joints[self.globalIDToLocalID[globalID]]

    def addJoint(self, joint: G1MSJoint, localID: int):
        parent = self.joints[self.localIDToGlobalID[joint.parentID]] # WIP: or self.joints[joint.parentID]
        # WIP: update, if parent has no abs_tm
        joint.abs_tm = calc_abs_rotation_position(joint, parent)
        while localID in self.localIDToGlobalID:
            localID += 10000
        i = self.header.jointCount
        self.localIDToGlobalID[localID] = i
        self.globalIDToLocalID[i] = localID
        self.joints.append(joint)
        self.header.jointCount += 1

@dataclass
class G1MGJointPaletteEntry:
    G1MMIndex: int
    physicsIndex: int
    jointIndex: int
    # def __post_init__(self):
    #     if self.jointIndex >> 31: # >= 0x80000000
    #         self.physicsIndex ^= 0x80000000
    #         self.jointIndex ^= 0x80000000

@dataclass
class G1MGJointPalette:
    jointCount: int
    joints: list[G1MGJointPaletteEntry]
    jointMapBuilder: list = field(default_factory=list) # useless on a class with overridden init

    def __init__(self, data: bytes, pos: int, internalSkel: G1MS = None, externalSkel: G1MS = None, globalToFinal: dict = None):
        self.jointCount, = unpack_from(E+'I', data, pos)
        self.joints = [G1MGJointPaletteEntry(*unpack_from(E+'3I', data, pos)) for pos in range(pos + 4, pos + 4 + self.jointCount * 12, 12)]
        # WIP: Possibly do this calculation later, externally, but uncomment __post_init__ above, The current code also causes an exception
        if internalSkel:
            for entry in self.joints:
                self.jointMapBuilder.append(
                    globalToFinal[
                        internalSkel.localIDToGlobalID.get(entry.jointIndex ^ 0x80000000) if externalSkel and entry.jointIndex >> 31 else \
                        externalSkel.localIDToGlobalID.get(entry.jointIndex) if externalSkel else \
                        internalSkel.localIDToGlobalID.get(entry.jointIndex)
                    ]
                )

# =================================================================
# VertexSpecs and Spec classes, used to store all attributes and values
# =================================================================

G1MG_VERTEXATTRIBUTE_STRUCT = '2H4B'
GVA_SZ = calcsize(G1MG_VERTEXATTRIBUTE_STRUCT)

@dataclass
class G1MGVertexAttribute:
    bufferID: int
    offset: int
    dataType: int|str # typeHandler: int
    dummyVar: int
    semantic: int|str # attribute: int
    layer: int

    def __post_init__(self):
        if self.dataType not in G1MGVAStructType: self.dataType = 0xFF
        # self.bufferID = vBufferIndices[self.bufferID]
        self.dataType = G1MGVAStructType[self.dataType]
        self.semantic = G1MGVASemantic[self.semantic] # Raises index out of range if not supported


@dataclass
class G1MGVertexAttributeSet:
    indexCount: int
    vBufferIndices: tuple[int]
    attributesCount: int
    attributes: list[G1MGVertexAttribute]

    def __init__(self, data: bytes, pos: int):
        self.indexCount, = unpack_from(E+'I', data, pos)
        i_end = pos + 4 * (self.indexCount + 1)
        self.vBufferIndices = unpack_from(f'{E} {self.indexCount}I', data, pos + 4)
        # Get all the attribute parameters
        self.attributesCount, = unpack_from(E+'I', data, i_end)
        self.attributes = [G1MGVertexAttribute(*unpack_from(E+G1MG_VERTEXATTRIBUTE_STRUCT, data, pos)) for pos in range(i_end + 4, i_end + 4 + self.attributesCount * GVA_SZ, GVA_SZ)]

    def get_vb_index(self, attribute_index: int) -> int:
        return self.vBufferIndices[self.attributes[attribute_index].bufferID]

"""
SPEC_STRUCT = '< '
@dataclass
class Spec:
    count: int
    List: list = []

class EG1MGVADatatype(Enum):
    Float_x1: int = 0x00
    Float_x2: int = 0x01
    Float_x3: int = 0x02
    Float_x4: int = 0x03
    UByte_x4: int = 0x05
    UShort_x4: int = 0x07
    UInt_x4: int = 0x09 # Need confirmation
    HalfFloat_x2: int = 0x0A
    HalfFloat_x4: int = 0x0B
    NormUByte_x4: int = 0x0D
    Dummy: int = 0xFF

class EG1MGVASemantic(Enum):
    Position: int = 0x00
    JointWeight: int = 0x01
    JointIndex: int = 0x02
    Normal: int = 0x03
    PSize: int = 0x04
    UV: int = 0x05
    Tangent: int = 0x06
    Binormal: int = 0x07
    TessalationFactor: int = 0x08
    PosTransform: int = 0x09
    Color: int = 0x0A
    Fog: int = 0x0B
    Depth: int = 0x0C
    Sample: int = 0x0D
"""

# G1MGVASemantic are upper camel case and mentioned in comments if worded differently
GLTF_Semantic = (
    'POSITION',
    'WEIGHTS', # JointWeight
    'JOINTS', # JointIndex
    'NORMAL',
    'PSIZE', # UV
    'TEXCOORD',
    'TANGENT',
    'BINORMAL',
    'TESSFACTOR', # TessalationFactor
    'POSITIONT', # PosTransform
    'COLOR',
    'FOG',
    'DEPTH',
    'SAMPLE'
)

# WIP: Replace all
G1MGVASemantic = (
    'Position'
    'JointWeight'
    'JointIndex'
    'Normal'
    'PSize'
    'UV'
    'Tangent'
    'Binormal'
    'TessalationFactor'
    'PosTransform'
    'Color'
    'Fog'
    'Depth'
    'Sample'
)

G1MGVAStructType = {
    0x00: 'f',
    0x01: '2f',
    0x02: '3f',
    0x03: '4f',
    0x05: '4B',
    0x07: '4H',
    0x09: '4I', # Need confirmation
    0x0A: '2e',
    0x0B: '4e',
    0x0D: 'BBBB', # NormUByte_x4: Seems to be handled identically to 4B (vertex colours?)
    0xFF: 'UNKNOWN' # Dummy
}

DATATYPE_TO_STRUCT = {
    8: 'B',
    16: 'H',
    32: 'I',
    64: 'Q'
}

# =================================================================
# Buffer class, used for vertex, index etc buffers
# =================================================================

@dataclass
class buffer_t:
    address: str = None
    stride: int = 12
    offset: int = 0
    dataType: int = None # = rpgeoDataType_e  RPGEODATA_FLOAT

@dataclass
class indexBuffer_t:
    address: str # = None
    indexCount: int
    dataType: int # rpgeoDataType_e
    primType: int # rpgeoPrimType_e

@dataclass
class mesh_t:
    posBuffer: buffer_t
    normBuffer: buffer_t
    uvBuffer: buffer_t
    blendIndicesBuffer: buffer_t
    blendWeightsBuffer: buffer_t
    indexBuffer: indexBuffer_t
    jointPerVertex: int # (B)

@dataclass
class G1MGVertexBuffer:
    unknown1: int
    stride: int
    count: int
    unknown2: int = 0
    offset: int = 0

@dataclass
class G1MGIndexBuffer:
    count: int
    dataType: str
    unknown1: int
    bitwidth: int
    offset: int

    def __init__(self, data: bytes, pos: int, version: int):
        self.count, dType, unk1 = unpack_from(E+'3I', data, pos)
        self.dataType = DATATYPE_TO_STRUCT[dType] # Note: causes an exception if not supported (yet)
        self.unknown1 = unk1 if version > 0x30303430 else -1 # old versions don't have this
        self.bitwidth = dType // 8
        self.offset = pos + (12 if version > 0x30303430 else 8)

# =================================================================
# Mesh, Material and LOD classes
# =================================================================

G1MG_MESH_STRUCT = '16s2H2I'
G1MG_MESHGROUP_STRUCT = '9I'
G1MG_SUBMESH_STRUCT = '14I'
G1MG_MESHGROUP_SIZE = calcsize(G1MG_MESHGROUP_STRUCT)
G1MG_M_SZ = calcsize(G1MG_MESH_STRUCT)

@dataclass
class G1MGMesh:
    name: bytes|str
    meshType: int # clothID
    unknown: int
    externalID: int # NUNID
    indexCount: int
    indices: tuple[int]
    data: InitVar[bytes]
    pos: InitVar[int]

    def __post_init__(self, data: bytes, pos: int):
        self.name = self.name.rstrip(b'\x00').decode()
        if self.indexCount > 0:
            self.indices = unpack_from(f'{E} {self.indexCount}I', data, pos)

@dataclass
class G1MGMeshGroup:
    LOD: int
    Group: int
    GroupEntryIndex: int
    submeshCount1: int # number of submeshes with 53 id
    submeshCount2: int # number of submeshes with 61 id
    lodRangeStart: int
    lodRangeLength: int
    unknown1: int
    unknown2: int
    meshes: list[G1MGMesh] = field(default_factory=list)

    def readMeshes(self, data: bytes, pos: int, version: int):
        pos += G1MG_MESHGROUP_SIZE
        # Fix info for old version:
        if version <= 0x30303430: # or 0x30303340 ?
            pos -= 16
            self.lodRangeStart = self.lodRangeLength = self.unknown1 = self.unknown2 = 0
        if version <= 0x30303330:
            pos -= 8
            self.submeshCount1 = self.Group
            self.submeshCount2 = self.GroupEntryIndex
            self.Group = self.GroupEntryIndex = 0
        # Read all submesh mesh info
        for _ in range(self.submeshCount1 + self.submeshCount2):
            mesh = G1MGMesh(*unpack_from(E+G1MG_MESH_STRUCT, data, pos), data=data, pos=pos + G1MG_M_SZ)
            self.meshes.append(mesh)
            pos += G1MG_M_SZ + max(mesh.indexCount, 1) * 4
        return pos

@dataclass
class G1MGSubmesh:
    submeshType: int # 53 or 61
    vertexBufferIndex: int
    bonePaletteIndex: int
    boneIndex: int # mat.palID according to vago's research
    unknown: int
    shaderParamIndex: int
    materialIndex: int
    indexBufferIndex: int
    unknown2: int
    indexBufferPrimType: int
    vertexBufferOffset: int
    vertexCount: int
    indexBufferOffset: int
    indexCount: int

G1MG_TEX_SZ = calcsize(E+'6H')
G1MG_MAT_SZ = calcsize(E+'4I')

@dataclass
class G1MGTexture:
    index: int = 0 # texture index in g1t file
    layer: int = 0 # TEXCOORD layer
    textureType: int = 0
    # Usually defines how a texture is packed.
    # For example when type = 0x2, and subtype = 0x19, it's usually Packed PBR
    # [0x2] 0x19 R = Specular, G = Smoothness, B = Metalness, A = Unused
    subtype: int = 0
    tileModeX: int = 0
    tileModeY: int = 0
    # key: str = 'UNKNOWN_0'

@dataclass
class G1MGMaterial:
    IDStart: int # unk1
    textureCount: int = 0
    idxType: int = 0 # unk2
    primType: int = 0 # unk3
    g1mgTextures: list[G1MGTexture] = field(default_factory=list)

@dataclass
class LOD:
    name: str = ''
    clothID: int = 0
    NUNID: int = 0
    indices: list = field(default_factory=list)

@dataclass
class LODList:
    count: int
    List: list

# =================================================================
# G1MG Other classes
# =================================================================

GSKT_SZ = 32

@dataclass
class G1MGSocket:
    bone_id: int
    unknown: int
    weight: float
    scale: tuple[float]
    position: tuple[float]
    def __init__(self, data: bytes, pos: int):
        self.bone_id, self.unknown, self.weight, *tuples = unpack_from(E+'2H7f', data, pos)
        self.scale, self.position = tuples[:3], tuples[3:]

@dataclass
class G1MGShader:
    size: int
    unk1: int
    buffer_type: int
    buffer_count: int
    name: str
    buffer: list[tuple]
    def __init__(self, data: bytes, pos: int):
        self.size, name_size, self.unk1, self.buffer_type, self.buffer_count = unpack_from(E+'3I2H', data, pos)
        self.name = unpack_from(f'{E} {name_size}s', data, pos + 16)[0].rstrip(b'\x00').decode()
        struct = 'i' if self.buffer_type == 5 else f'{self.buffer_type}f' if self.buffer_type < 5 else 'x' # 'i' or 'I'?
        s = calcsize(struct)
        pos += 16 + name_size
        self.buffer = [unpack_from(E+struct, data, p) for p in range(pos, pos + s * self.buffer_count, s)]

# =================================================================
# G1M Class, with all the containers for the model
# =================================================================

@dataclass
class G1MHeader:
    firstChunkOffset: int
    reserved1: int
    chunkCount: int

@dataclass
class G1MG(GResourceHeader):
    platform: str
    reserved: int
    bounding_box: dict
    sectionCount: int
    meshCount: int # not (yet) used (?)
    geometry_sockets: list
    materials: list[G1MGMaterial]
    shader_params: list
    vertex_buffers: list[G1MGVertexBuffer]
    vertexAttributeSets: list[G1MGVertexAttributeSet]
    joint_palettes: list[G1MGJointPalette]
    index_buffers: list[G1MGIndexBuffer]
    submeshes: list[G1MGSubmesh]
    meshGroups: list[G1MGMeshGroup] # mesh_lod
    # WIP: These list might have to be put in a single list with an id for each list entry, to preserve the order
    # meshInfo: list = []
    # boneMaps: list = []
    # boneMapListCloth: list = []
    # spec: list = []
    # texture: list = []

    def __init__(self, data: bytes, pos: int, internalSkel: G1MS = None, externalSkel: G1MS = None, globalToFinal: dict = None):
        # Read headers (size hardcoded), WIP: could use better inheritance and create the bounding_box on serialization
        self.magic, self.chunkVersion, self.chunkSize = unpack_from(E+'4s2I', data, pos)
        g1mgHeader = G1MGHeader(*unpack_from(E+G1MG_HEADER_STRUCT, data, pos + 12))
        self.magic = self.magic.decode()
        self.platform = g1mgHeader.platform.decode()
        self.reserved = g1mgHeader.reserved
        self.bounding_box = dict(list(g1mgHeader.__dict__.items())[2:8]) # WIP: This is kinda broken, maybe I just should add the G1MGHeader
        self.sectionCount = g1mgHeader.sectionCount
        # WIP: The following 7 lists will be expanded by additional matching subsections if they exist. The others not
        self.materials = self.shader_params = self.vertex_buffers = self.vertexAttributeSets = self.joint_palettes = self.index_buffers = self.meshGroups = []
        sms = calcsize(G1MG_SUBMESH_STRUCT)
        pos += 12 + calcsize(G1MG_HEADER_STRUCT)
        for _ in range(g1mgHeader.sectionCount):
            section = G1MGSubSectionHeader(*unpack_from(E+III_STRUCT, data, pos))
            end = pos + section.size
            pos += 12
            match section.magic:
                case 0x00010001:
                    self.geometry_sockets = [{
                        'id_referenceonly': i,
                        'start': G1MGSocket(data, pos + GSKT_SZ * 2 * i),
                        'end': G1MGSocket(data, pos + GSKT_SZ * 2 * i + GSKT_SZ)}
                        for i in range(section.count)]
                    ssz = GSKT_SZ * 2 * section.count
                    self.geometry_sockets.append(unpack_from(f'{E} {(section.size - ssz - 12) // 4}I', data, pos + ssz))
                case 0x00010002:
                    for _ in range(section.count):
                        mat = G1MGMaterial(*unpack(E+'4I', data, pos))
                        pos += G1MG_MAT_SZ
                        mat.g1mgTextures = [G1MGTexture(*unpack_from(E+'6H', data, p)) for p in range(pos, pos + mat.textureCount * G1MG_TEX_SZ, G1MG_TEX_SZ)]
                        self.materials.append(mat)
                        pos += mat.textureCount * G1MG_TEX_SZ
                case 0x00010003:
                    for _ in range(section.count):
                        shader_info = []
                        for _ in range(unpack_from(E+'I', data, pos)):
                            shader = G1MGShader(*unpack_from(E+III_STRUCT, data, pos + 4))
                            shader_info.append(shader)
                            pos += shader.size
                        self.shader_params.append(shader_info)
                case 0x00010004:
                    for _ in range(section.count):
                        vs = 4 if self.chunkVersion > 0x30303430 else 3
                        vb = G1MGVertexBuffer(*unpack_from(f'{E} {vs}I', data, pos))
                        vb.offset = pos + vs * 4
                        # vb.data = unpack_from(f'{E} {vb.count * vb.stride}s', data, pos + vs * 4) # skipping, might store buffer or offset in the future
                        self.vertex_buffers.append(vb)
                        pos += vs * 4 + vb.stride * vb.count
                case 0x00010005:
                    for _ in range(section.count):
                        va = G1MGVertexAttributeSet(data, pos)
                        self.vertexAttributeSets.append(va)
                        pos += 8 + 4 * va.indexCount + GVA_SZ * va.attributesCount
                case 0x00010006:
                    for _ in range(section.count):
                        jp = G1MGJointPalette(data, pos, internalSkel, externalSkel, globalToFinal)
                        self.joint_palettes.append(jp)
                        pos += jp.jointCount * 12 + 4
                case 0x00010007:
                    for _ in range(section.count):
                        ib = G1MGIndexBuffer(data, pos, self.chunkVersion)
                        self.index_buffers.append(ib)
                        # ib.data = unpack_from(f'{E} {ib.count}{ib.dataType?}', data, ib.offset) # skipping, might store buffer or offset in the future
                        pos += ib.offset + ib.count * ib.bitwidth
                        pos += (4 - pos) % 4
                case 0x00010008:
                    end = pos + section.count * sms
                    self.submeshes = [G1MGSubmesh(*unpack_from(E+G1MG_SUBMESH_STRUCT, data, p)) for p in range(pos, end, sms)]
                    pos = end
                case 0x00010009:
                    for _ in range(section.count):
                        mg = G1MGMeshGroup(*unpack_from(E+G1MG_MESHGROUP_STRUCT, data, pos))
                        pos += mg.readMeshes(data, pos, self.chunkVersion)
                        self.meshGroups.append(mg)
                # case _:
                #   self.unknown.append('UNKNOWN')
            pos = end

    def get_vb(self, submesh_vb_index: int, semantic: str, data: bytes, layer_threshold: int = -1):
        for a in self.vertexAttributeSets[submesh_vb_index].attributes:
            if a.semantic == semantic and a.layer > layer_threshold:
                vb = self.vertex_buffers[self.vertexAttributeSets[submesh_vb_index].vBufferIndices[a.bufferID]]
                return (unpack_from(f'{E} {a.dataType}', data, p) for p in range(vb.offset + a.offset, vb.offset + a.offset + vb.count * vb.stride, vb.stride))
        return iter(())

# =================================================================
# Matrix data
# =================================================================

@dataclass
class G1MM:
    matrixCount: int
    matrices: bytes
    def __init__(self, data: bytes, pos: int):
        """
        Read G1MM section, sans Gust header (G1MM magic, version, size)
        Header size = 12
        WIP: Needs to be converted
        """
        self.matrixCount, = unpack_from(E+'I', data, pos + 12)
        self.matrices = data[pos + 16:pos + 16 + self.matrixCount * 64]

"""
# =================================================================
# Buffer Functions
# =================================================================

# WIP: Uses Noesis tools
https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/Utils.h#L567
def createDriverVertexBuffers(dMesh: mesh_t, cpSize:int, unpooledBufs: list):
    # dMesh.posBuffer.dataType = rpgeoDataType_e  RPGEODATA_FLOAT
    dMesh.posBuffer.address = noeRAPI_t.Noesis_UnpooledAlloc(4 * 3 * cpSize)
	dMesh.posBuffer.stride = 12
    unpooledBufs.append(dMesh.posBuffer.address)
    float* posB = (float*)dMesh.posBuffer.address

https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/Utils.h#L589
def createDriverIndexBuffers
"""

# =================================================================
# Common Functions
# =================================================================

def calc_abs_rotation_position(bone: G1MSJoint, parent_bone: G1MSJoint) -> ndarray:
    """
    Takes quat/pos relative to parent, and reorients / moves to be relative to the origin.
    Parent bone must already be transformed.
    WIP: This should probably be calculated when used (but Keep)
    """
    q1 = Quaternion(bone.rotation)
    qp = Quaternion(matrix=parent_bone.abs_tm)
    abs_tm = (qp * q1).unit.transformation_matrix
    abs_tm[3,:3] = (qp.rotate(bone.position) + parent_bone.abs_tm[3,:3])
    return abs_tm

def name_bones(skel_data: G1MS, oid: dict) -> G1MS:
    """WIP: Can probably be simplified and used on the go (no function)"""
    for i, bone in enumerate(skel_data.joints): # range(skel_data.header.jointCount)
        # bone_id_auto might be important
        # index of joint to index of joint indices ID. WIP: Is this correct? shouldn't it be globalIDToLocalID ?
        bone_id_auto = skel_data.localIDToGlobalID[i]
        if bone_id_auto in oid:
            skel_data.joints[i].name = oid[bone_id_auto] # OID seems to line up with joint indices? WIP: Need a clear idea how to ID, + name is not an existing attribute
    return skel_data

def combine_skeleton(base_skel_data: G1MS, model_skel_data: G1MS) -> dict:
    # WIP: Could possibly go without externalOffset, etc. and return a G1MS object (this is for layering, though)
    if model_skel_data.header.jointIndicesCount == len(base_skel_data.globalIDToLocalID):
        return base_skel_data
    else:
        combined_data = base_skel_data.__dict__
        combined_data['externalOffset'] = len(base_skel_data.globalIDToLocalID)
        combined_data['externalOffsetList'] = base_skel_data.header.jointCount # ?
        for i, ID in enumerate(model_skel_data.header.globalIDToLocalID):
            if i >= combined_data['externalOffset'] or i == 0:
                combined_data['globalIDToLocalID'].append(ID + combined_data['externalOffsetList'] + 1)
            if (ID != 0xFFFF and i != 0):
                combined_data['localIDToGlobalID'][ID + combined_data['externalOffsetList']] = i
        for i, bone in enumerate(model_skel_data.joints):
            combined_data['externalOffsetMax'] += 1
            # bone['bone_id'] = 'Clothbone_' + str(i)
            if bone.parent < 0: bone.parent &= 0xFFFF # WIP: since we unpack I instead of i, this logic doesn't work
            else: bone.parent += combined_data['externalOffsetList']
            combined_data['joints'].append(calc_abs_rotation_position(bone, combined_data['joints'][bone.parent]))
        return combined_data

# =================================================================
# NUN, Cloth, Physique Functions
# =================================================================

def calc_nun_maps(nun_data: list, skel: G1MS) -> dict:
    """
    WIP
    Calculate vertices and bones from all Nun entries (NUNO1-5, NUNS1, NUNV1)
    This should be done after reading one (or multiple?) G1M files completely
    """
    nun_maps = {
        'clothMap': [],
        'clothParentIDMap': [],
        'driverMeshList': []
    }
    boneCount = skel.header.jointCount
    for nun in nun_data:
        nunMap = [] # ?
        boneStart = boneCount # ?
        parentBone = skel.globalIDToLocalID[nun.parentBoneID] # WIP: parentBoneID must be globalID for this, but it might be wrong
        for pointIndex, cp in enumerate(nun.controlPoints):
            link = nun.influences[pointIndex] # cp and influences have an identical count
            nunMap.append(boneCount)
            parentID = link.P3
            parentID_bone = skel.joints[parentBone] # WIP: What to do if fails?
            # transform_point_info['p'] = list(cp[:3])
            # transform_point_info['parentID'] = link.P3
            # transform_point_info['parentBone'] = parentBone
            p = cp[:3] # cp are 3 or 4 floats
            if parentID == -1:
                parentID = parentBone
                q = Quaternion()
            else:
                parentID += boneStart # WIP: layers?
                q = Quaternion(matrix=parentID_bone.abs_tm)
                pp = parentID_bone.abs_tm[3,:3]
                parentID_bone = skel.joints[parentID]
                # p = (numpy.array(q.rotate(p)) + pp).tolist()
                # 4x3 inversion appears to be 4x4 inversion with xyzw in the column, not row (is this correct?)
                qpi = Quaternion(matrix=parentID_bone.abs_tm).inverse
                q *= qpi
                t = parentID_bone.abs_tm
                t[:3,3] = t[3,:3]
                p = (np.linalg.inv(t)[:3,3] + q.rotate(p) + qpi.rotate(pp)).tolist()
            bone = G1MSJoint(
                1.0, 1.0, 1.0,
                *q, q[1]
                *p, 0.0)
            bone.parentID = parentID # + parentBone?
            bone.abs_tm = calc_abs_rotation_position(bone, skel.joints[parentID])
            # bone.bone_id = f'nuno1bone_p{parentBone}_{boneCount}'?
            # transform_point_info['bone_name'] = f'nuno1bone_p{parentBone}_{boneCount}'
            # transform_point_info['abs_tm'] = bone.abs_tm
            # transform_point_info['NewparentID'] = parentID
            # transform_point_info['updatedPosition'] = (bone.abs_tm[3,:3] + Quaternion(matrix=bone.abs_tm).rotate([0.0, 0.0, 0.0]))).tolist()
            # transform_info.append(transform_point_info)
            # vertices.append(transform_point_info['updatedPosition'])
            # skin_weights.append((1.0, 0.0, 0.0, 0.0))
            # skinIndiceList.append((boneCount, 0, 0, 0))
            skel.joints.append(bone)
            boneCount += 1
            if link.P1 > 0 and link.P3 > 0:
                # triangles.append(pointIndex, link.P1, link.P3)
                pass
            if link.P2 > 0 and link.P4 > 0:
                # triangles.append(pointIndex, link.P2, link.P4)
                pass
        # WIP: This is a different driver mesh! Need a unified class or two classes
        # Might change this, depending on what is needed in the end
        nun_maps['clothMap'].append(nunMap)
        nun_maps['clothParentIDMap'].append(parentBone)
        nun_maps['driverMeshList'].append(DriverMesh(
            vertCount = pointIndex + 1,
            vertices = [
                DriverMeshEntry(0, 'POSITION', Buffer = vertices),
                DriverMeshEntry(0, 'BLENDWEIGHT', Buffer = skin_weights),
                DriverMeshEntry(0, 'BLENDINDICES', Buffer = skinIndiceList)
            ],
            indices = triangles,
            transform_info = transform_info
        ))
        # Dummy fallback entry if it fails? Some entries lack the info, such as NUNO2
    return nun_maps

def compute_center_of_mass(position: tuple, weights: tuple, bones_indices: tuple, nun_bones: list[G1MSJoint]):
    # nun_bones must correspond with the control points and have abs_tm already
    temp = (0,0,0)
    for bone_num, bone_idx in enumerate(bones_indices):
        tm = nun_bones[bone_idx].abs_tm
        temp += Quaternion(matrix=tm).rotate(position) + tm[3,:3] * weights[bone_num]
    return temp

def find_submeshes(subvbs: list[G1MGSubmesh]):
    """
    Build a quick dictionary of the meshes, each with a list of submesh indices.
    This enables subvbs[vbsubs[vertexBufferIndex][0]] instead of next(s for s in subvbs if s.vertexBufferIndex == vertexBufferIndex).
    """
    vbsubs = {x: [] for x in {s.vertexBufferIndex for s in subvbs}}
    for i, s in enumerate(subvbs):
        vbsubs[s.vertexBufferIndex].append(i)
    return vbsubs

"""Generate fmt structures from metadata
def generate_fmts(g1mg: G1MG):
    # WIP: eArmada8 only used first list per type (unknown if more are possible)
    fmts = []
    for i, vas in enumerate(g1mg.vertexAttributeSets):
        # insert extra dummy, so AlignedByteOffset is calculated correctly (?)
        vb_strides = [0] + [g1mg.vertex_buffers[bi].stride for bi in vas.vBufferIndices]
        fmt_elements = []
        for j, attr in enumerate(vas.attributes):
            # Input Slot is set to zero, and AlignedByteOffset is set to offset + vb_strides[input slot]
            # because blender plugin does not support multiple input slots.
            # WIP: Since we aim to calculate things direclty, this data should probably be carried differently
            fmt_elements.append({
                'id': str(j),
                'SemanticName': attr.semantic,
                'SemanticIndex': attr.layer,
                'Format': attr.dataType,
                'InputSlot': '0',
                'AlignedByteOffset': attr.offset + vb_strides[attr.bufferID],
                'InputSlotClass': 'per-vertex',
                'InstanceDataStepRate': '0'})
        # For some reason, topology is stored in submesh instead of vertex attributes
        # THRG says type 1 is Quad, dunno what that is, it's not in DX11?
        ibpt = next(s.indexBufferPrimType for s in g1mg.submeshes if s.vertexBufferIndex == i)
        fmts.append({
            'stride': str(sum(vb_strides)),
            'topology': 'pointlist' if ibpt == 1 else 'trianglelist' if ibpt == 3 else 'trianglestrip' if  ibpt == 4 else 'undefined',
            'format': g1mg.index_buffers[i].dataType,
            'elements': fmt_elements
            })
    return fmts
"""

def generate_ib(ib: G1MGIndexBuffer, data: bytes):
    """Read the index buffer bytes in a tuple. WIP: The format might return tuples, and the definitive buffer reader uses the format's return (tuples/lists)"""
    return unpack_from(f'{E} {ib.count}{ib.dataType}', data, ib.offset)
    """Read the index buffer bytes in a list of tuples of three (triangles)."""
    return [unpack_from(f'{E} 3{ib.dataType}', data, p) for p in range(ib.offset, ib.offset + ib.bitwidth * ib.count, ib.bitwidth * 3)]

def trianglestrip_to_list(ib_list: list) -> list:
    return [x for i in range(0, len(ib_list) - 2, 2)
            for x in ((ib_list[i], ib_list[i + 1], ib_list[i + 2]),
                      (ib_list[i + 1], ib_list[i + 3], ib_list[i + 2]))] # DirectX implementation
                      # (ib_list[i + 2], ib_list[i + 1], ib_list[i + 3]) # OpenGL implementation

def generate_vb(index: int, data: bytes, g1mg: G1MG):
    if index >= len(g1mg.vertexAttributeSets): return None
    vbis = g1mg.vertexAttributeSets[index].vBufferIndices
    vb_struct = []
    # WIP: My test file had a single buffer index on each attribute set
    for a in g1mg.vertexAttributeSets[index].attributes:
        # Since vBufferIndices seem to correspond with the list indices [0, 1, 2, ...], we could possibly use g1mg.vertex_buffers[a.bufferID]
        if g1mg.vertex_buffers[vbis[0]].count < 2: a.bufferID = 0 # usually is 0 anyway, but it doesn't really make sense to me to use (or even read) the same buffer multiple times
        _vb = g1mg.vertex_buffers[vbis[a.bufferID]]
        vb_struct.append({
            'SemanticName': a.semantic,
            'SemanticIndex': a.layer,
            'Buffer': (unpack_from(f'{E} {a.dataType}', data, p) for p in range(_vb.offset + a.offset, _vb.offset + a.offset + _vb.count * _vb.stride, _vb.stride))
        })
        # WIP: If possible, the vertices should be processed right here. Could possibly use iter_unpack
        # Note: G1MGVertexAttribute.offset is usually 0. Unknown if it corresponds to bytes of dataType if not 0.
        # Note: If there's only one buffer (and ID is consequently 0 in every attribute), this reads the same buffer multiple times.
        #       WIP: For a better code, I need to know how this data is parsed, first
        # Note: Some say that all buffers (if multiple) should be capped to first_vb.count (zip would do the same, but I don't know if we need zip, as the original code seems to re-order them)
    return vb_struct

def cull_vb(submesh: dict) -> dict:
    # WIP: Update according to definitive format. This function might end up unused
    # Original was called by default, but G1M Tools doesn't use it
    # ib must be 2 dimensional
    new_vb = []
    for i in range(len(submesh['vb'])):
        new_vb.append({'SemanticName': submesh['vb'][i]['SemanticName'],\
            'SemanticIndex': submesh['vb'][i]['SemanticIndex'], 'Buffer': []})
    new_indices = {}
    current_vertex = 0
    # again, only the first buffer...
    for i in sorted({x for l in submesh['ib'] for x in l if i < len(submesh['vb'][0]['Buffer'])}):
        for j, vb in enumerate(submesh['vb']):
            new_vb[j]['Buffer'].append(vb['Buffer'][i])
        new_indices[i] = current_vertex
        current_vertex += 1
    submesh['vb'] = new_vb
    for i in range(len(submesh['ib'])):
        for j in range(len(submesh['ib'][i])):
            submesh['ib'][i][j] = new_indices[submesh['ib'][i][j]]
    return submesh

def generate_vgmap(boneindex: int, g1mg: G1MG, skel_data: G1MS):
    # WIP: return {skel_data.getGlobalID(j.jointIndex): i * 3 for i, j in enumerate(g1mg.joint_palettes[boneindex].joints)}
    if skel_data.header.jointCount < 2: return # WIP
    return {skel_data.localIDToGlobalID[j.jointIndex ^ 0x80000000 if not skel_data.bIsInternal and j.jointIndex >> 31 else \
                                        j.jointIndex]: i * 3
               for i, j in enumerate(g1mg.joint_palettes[boneindex].joints)
           } # f'bone_{skel_data.localIDToGlobalID[j.jointIndex]}' = i * 3

def write_submeshes(data: bytes, g1mg: G1MG, skel_data: G1MS, nun_maps = None, path = '', e = '<', cull_vertices: bool = False,\
        write_empty_buffers: bool = False, preserve_trianglestrip: bool = False):
    # WIP: The main part of this should probably be in MUA3_G1
    if nun_maps:
        # WIP: To remove
        # nun_maps contains the nun_data and the calculated data
        pass
    cloth_render_fail = False
    for subindex, submesh in enumerate(g1mg.submeshes):
        print("Processing submesh {0}...".format(subindex))
        # submesh = {'fmt': fmts[submesh.vertexBufferIndex]}
        ib_data = generate_ib(g1mg.index_buffers[submesh.indexBufferIndex], data)
        # WIP: For flatten, culling, etc. Numpy might be a good module to use
        # Originally: Flatten from 2D to 1D before sectioning, but why was it read as 2D to begin with?
        #             ib = [x for y in ib_data for x in y][submesh.indexBufferOffset:submesh.indexBufferOffset + submesh.indexCount]
        if submesh.indexBufferPrimType == 4 and preserve_trianglestrip == False: # (1 prim, 3 triangle, 4 trianglestrip)
            ib = trianglestrip_to_list(ib_data)
            # submesh["fmt"]["topology"] = "trianglelist"
        else:
            # or triangles?: ib = [ib[i:i + 3] for i in range(0, len(ib), 3)]
            ib = [[x] for x in ib_data] # Turn (back) into 2D list so cull_vertices() works
        vb = generate_vb(submesh.vertexBufferIndex, data, g1mg) # vertexBufferIndex seems to correspond with vertexAttributeSets
        if cull_vertices == True:
            submesh = cull_vb(submesh)
        # Trying to detect if the external skeleton is missing
        if skel_data.bIsInternal:
            vgmap = generate_vgmap(submesh.bonePaletteIndex, g1mg, skel_data)
        else:
            vgmap = False # G1M uses external skeleton that isn't available
        # WIP: Need to build nun_bones with abs_tm, relative to parent bone of skel_data with all bones calculated abs_tm and find a way to combine the bones with a hierarchy
        #      could probably use skel_data.addJoint(bone, ?), but need a way to export the data to the skeleton that will be imported/exported
        #      would probably use most of what is in calc_nun_maps

        # AT THIS POINT, THE DATA SHOULD BE READY FOR THE BLENDER PLUGIN
        # WIP: Just need to know what information's needed for further conversion
        # write_fmt(submesh['fmt'], f'{path}{subindex}.fmt')
        # if len(ib) > 0 or write_empty_buffers == True:
        #     write_ib(ib, f'{path}{subindex}.ib', submesh['fmt'])
        #     write_vb(vb, f'{path}{subindex}.vb', submesh['fmt'])
        # if vgmap:
        #     with open(f'{path}{subindex}.vgmap', 'w') as f:
        #         json.dump(data, f, indent=4)
        submesh_lod = next(x for y in g1mg.meshGroups for x in y.meshes if subindex in x.indices)
        if not cloth_render_fail and not nun_maps == False and transform_cloth: # probably check for nun joints instead of nun_maps
            try:
                if submesh_lod.meshType == 1:
                    NUNID = mesh.externalID % 10000
                    if -1 < mesh.externalID and mesh.externalID < 10000:
                        # nun = NUNOs[WIP].Nuno1[NUNID]
                        pass
                    elif mesh.externalID < 20000:
                        # nun = NUNVs[WIP].Nunv1[NUNID]
                        pass
                    elif mesh.externalID < 30000:
                        # WIP: NUNO3 and NUNO5
                        pass
                    cloth_parent_bone = skel_data.getJoint(nun.parentBoneID)
                    position_data = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Position', data))
                    normal_data = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Normal', data))
                    blend_indices = list(g1mg.get_vb(submesh.vertexBufferIndex, 'JointIndex', data))
                    skin_weights = list(g1mg.get_vb(submesh.vertexBufferIndex, 'JointWeight', data))
                    cloth_stuff_1_b = list(g1mg.get_vb(submesh.vertexBufferIndex, 'PSize', data))
                    cloth_stuff_2_b = list(g1mg.get_vb(submesh.vertexBufferIndexsubmesh.vertexBufferIndex, 'UV', data, 2)) # Not really sure
                    # cloth_stuff_3_b = [x[3] for x in g1mg.get_vb(submesh.vertexBufferIndex, 'Position', data)]
                    cloth_stuff_4_b = [x[3] for x in g1mg.get_vb(submesh.vertexBufferIndex, 'Normal', data)]
                    cloth_stuff_5_b = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Color', data, 0))
                    tangent_data = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Tangent', data))
                    binormal_buffer = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Binormal', data))
                    fog_buffer = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Fog', data))
                    cpc = len(nun.controlPoints)
                    # drivermesh = DriverMesh(
                    #     vertCount = cpc,
                    #     vertices = [
                    #         DriverMeshEntry(0, 'POSITION', Buffer = vertices),
                    #         DriverMeshEntry(0, 'BLENDWEIGHT', Buffer = [(1.0, 0.0, 0.0, 0.0) for _ in range(cpc)]),
                    #         DriverMeshEntry(0, 'BLENDINDICES', Buffer = [(boneCount, 0, 0, 0) for boneCount in range(cpc)])
                    #     ],
                    #     indices = triangles,
                    #     transform_info = transform_info
                    # )
                    vertPosBuff = []
                    vertNormBuff = []
                    tangentBuffer = []
                    for i, clothPosition in enumerate(position_data):
                        if binormal_buffer[i] == (0,0,0,0):
                            vertPosBuff.append(Quaternion(matrix=cloth_parent_bone.abs_tm).rotate(clothPosition[:3]) + cloth_parent_bone.abs_tm[3,:3])
                            vertNormBuff.append(normal_data[i])
                            if tangent_data: tangentBuffer.append(tangent_data[i])
                        else:
                            a = (0, 0, 0)
                            a += compute_center_of_mass((0, 0, 0), clothPosition, blend_indices[i], nun_bones) * skin_weights[i][0]
                            a += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_1_b[i], nun_bones) * skin_weights[i][1]
                            a += compute_center_of_mass((0, 0, 0), clothPosition, fog_buffer[i], nun_bones) * skin_weights[i][2]
                            a += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_2_b[i], nun_bones) * skin_weights[i][3]
                            b = (0, 0, 0)
                            b += compute_center_of_mass((0, 0, 0), clothPosition, blend_indices[i], nun_bones) * cloth_stuff_5_b[i][0]
                            b += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_1_b[i], nun_bones) * cloth_stuff_5_b[i][1]
                            b += compute_center_of_mass((0, 0, 0), clothPosition, fog_buffer[i], nun_bones) * cloth_stuff_5_b[i][2]
                            b += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_2_b[i], nun_bones) * cloth_stuff_5_b[i][3]
                            c = (0, 0, 0)
                            c += compute_center_of_mass((0, 0, 0), binormal_buffer[i], blend_indices[i], nun_bones) * skin_weights[i][0]
                            c += compute_center_of_mass((0, 0, 0), binormal_buffer[i], cloth_stuff_1_b[i], nun_bones) * skin_weights[i][1]
                            c += compute_center_of_mass((0, 0, 0), binormal_buffer[i], fog_buffer[i], nun_bones) * skin_weights[i][2]
                            c += compute_center_of_mass((0, 0, 0), binormal_buffer[i], cloth_stuff_2_b[i], nun_bones) * skin_weights[i][3]
                            d = np.cross(b,c)
                            vertPosBuff.append((d / np.linalg.norm(d) if is_nuno else d) * cloth_stuff_4_b[i] + a)
                            e = b * normal_data[i][1] + c * normal_data[i][0] + d * normal_data[i][2]
                            vertNormBuff.append(e / np.linalg.norm(e))
                            if tangent_data:
                                e = b * tangent_data[i][1] + c * tangent_data[i][0] + d * tangent_data[i][2]
                                tangentBuffer.append((e / np.linalg.norm(e)).tolist() + [tangent_data[i][3]])

                    # write_fmt(transformed_submesh['fmt'],f'{path}{subindex}_transformed.fmt')
                    # if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                    #     write_ib(transformed_submesh['ib'],f'{path}{subindex}_transformed.ib', transformed_submesh['fmt'])
                    #     write_vb(transformed_submesh['vb'],f'{path}{subindex}_transformed.vb', transformed_submesh['fmt'])
                    # if not transformed_submesh["vgmap"] == False:
                    #     with open('{0}{1}_transformed.vgmap'.format(path, subindex), 'wb') as f:
                    #         f.write(json.dumps(transformed_submesh['vgmap'], indent=4).encode("utf-8"))
                    # write_fmt(driverMesh_fmt,'{0}{1}_drivermesh.fmt'.format(path, subindex))
                    # if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                    #     write_ib(drivermesh['indices'],'{0}{1}_drivermesh.ib'.format(path, subindex), driverMesh_fmt)
                    #     write_vb(drivermesh['vertices'],'{0}{1}_drivermesh.vb'.format(path, subindex), driverMesh_fmt)
                if submesh_lod.meshType == 2:
                    # Doesn't seem to be SOFT. What is it, though?
                    palette = g1mg.joint_palettes[submesh.bonePaletteIndex]
                    physicsBoneList = [x.physicsIndex & 0xFFFF for x in palette]
                    phys_bone_count = len(physicsBoneList)
                    position_data = list(g1mg.get_vb(submesh.vertexBufferIndex, 'Position', data))
                    oldSkinIndiceList = list(g1mg.get_vb(submesh.vertexBufferIndex, 'JointIndex', data)) # instead of blend_indices
                    if not oldSkinIndiceList: oldSkinIndiceList = [(0, 0, 0, 0)] * len(position_data)
                    vertPosBuff = []
                    for i, clothPosition in enumerate(position_data):
                        index = oldSkinIndiceList[i][0] // 3 # JointIndex // 3 ?
                        if index < phys_bone_count and index < model_skel_data.header.jointCount:
                            tm = model_skel_data.joints[index].abs_tm
                            q1 = Quaternion(matrix=tm)
                            q2 = Quaternion([q1[0], 0-q1[1], 0-q1[2], 0-q1[3]]) * Quaternion(0, position_data[i][0], position_data[i][1], position_data[i][2]) * q1
                            vertPosBuff.append(tm[3,:3] + (q2[1], q2[2], q2[3]))

                    # if remove_physics == True: semantics_to_keep = ['Position', 'JointWeight', 'JointIndex', 'Normal', 'Color', 'UV', 'Tangent'] # is this option useful?

                    # write_fmt(transformed_submesh['fmt'],'{0}{1}_transformed.fmt'.format(path, subindex))
                    # if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                    #     write_ib(transformed_submesh['ib'],'{0}{1}_transformed.ib'.format(path, subindex), transformed_submesh['fmt'])
                    #     write_vb(transformed_submesh['vb'],'{0}{1}_transformed.vb'.format(path, subindex), transformed_submesh['fmt'])
            except:
                cloth_render_fail = True
                print("Rendering cloth mesh failed! Cloth mesh rendering will be skipped.")

# =================================================================
# Parsing Functions
# =================================================================

# The argument passed (g1m_name) is actually the folder name | WIP: To remove
def parseG1M(g1m_name, overwrite = False, write_buffers = True, cull_vertices = True, transform_cloth = True, write_empty_buffers = False, preserve_trianglestrip = False):
    with open(g1m_name + '.g1m', "rb") as f:
        print("Processing {0}...".format(g1m_name + '.g1m'))
        file = {}
        nun_struct = {}
        file["file_magic"], = unpack(">I", f.read(4))
        if file["file_magic"] == 0x5F4D3147:
            e = '<' # Little Endian
        elif file["file_magic"] == 0x47314D5F:
            e = '>' # Big Endian
        else:
            print("not G1M!") # Figure this out later
            return
        file["file_version"], = unpack(e+"I", f.read(4))
        file["file_size"], = unpack(e+"I", f.read(4))
        chunks = {}
        chunks["starting_offset"], chunks["reserved"], chunks["count"] = unpack(e+"III", f.read(12))
        chunks["chunks"] = []
        f.seek(chunks["starting_offset"])
        have_skeleton = False
        nun_parse_fail = False
        for i in range(chunks["count"]):
            chunk = {}
            chunk["start_offset"] = f.tell()
            chunk["magic"] = f.read(4).decode("utf-8")
            chunk["version"] = f.read(4).hex()
            chunk["size"], = unpack(e+"I", f.read(4))
            chunks["chunks"].append(chunk)
            if chunk["magic"] in ['G1MS', 'SM1G'] and have_skeleton == False:
                f.seek(chunk["start_offset"],0)
                model_skel_data = parseG1MS(f.read(chunk["size"]),e)
                if os.path.exists(g1m_name+'Oid.bin'):
                    model_skel_oid = binary_oid_to_dict(g1m_name+'Oid.bin')
                    model_skel_data = name_bones(model_skel_data, model_skel_oid)
                if model_skel_data['jointCount'] > 1 and not model_skel_data['boneList'][0]['parentID'] < -200000000:
                    #Internal Skeleton
                    model_skel_data = calc_abs_skeleton(model_skel_data)
                else:
                    ext_skel = get_ext_skeleton(g1m_name)
                    if not ext_skel == False:
                        model_skel_data = combine_skeleton(ext_skel, model_skel_data)
                have_skeleton = True # I guess some games duplicate this section?
            elif chunk["magic"] in ['NUNO', 'ONUN', 'NUNV', 'VNUN', 'NUNS', 'SNUN'] and transform_cloth == True:
                try:
                    f.seek(chunk["start_offset"],0)
                    if chunk["magic"] in ['NUNO', 'ONUN']: # NUNO
                        nun_struct["nuno"] = parseNUNO(f.read(chunk["size"]),e)
                    elif chunk["magic"] in ['NUNV', 'VNUN']: # NUNV
                        nun_struct["nunv"] = parseNUNV(f.read(chunk["size"]),e)
                    elif chunk["magic"] in ['NUNS', 'SNUN']: # NUNS
                        nun_struct["nuns"] = parseNUNS(f.read(chunk["size"]),e)
                except:
                    nun_parse_fail = True
                    print("Parsing cloth mesh NUN data failed!  Cloth mesh rendering will be skipped.")
                    f.seek(chunk["start_offset"] + chunk["size"],0)
            elif chunk["magic"] in ['G1MG', 'GM1G']:
                f.seek(chunk["start_offset"],0)
                g1mg_stream = f.read(chunk["size"])
                model_mesh_metadata = parseG1MG(g1mg_stream,e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
        nun_maps = False
        if len(nun_struct) > 0 and model_skel_data['jointCount'] > 1 and transform_cloth == True:
            try:
                nun_data = stack_nun(nun_struct)
                nun_maps = calc_nun_maps(nun_data, model_skel_data)
                if not nun_maps == False:
                    nun_maps['nun_data'] = nun_data
            except:
                print("Compiling cloth mesh NUN data failed!  Cloth mesh rendering will be skipped.")
        if os.path.exists(g1m_name) and (os.path.isdir(g1m_name)) and (overwrite == False):
            if str(input(g1m_name + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(g1m_name):
            if not os.path.exists(g1m_name):
                os.mkdir(g1m_name)
            with open(g1m_name+"/mesh_metadata.json", "wb") as f:
                f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
            #with open(g1m_name+"/skel_data.json", "wb") as f:
                #f.write(json.dumps(model_skel_data, indent=4).encode("utf-8"))
            if write_buffers == True:
                write_submeshes(g1mg_stream, model_mesh_metadata, model_skel_data,\
                    nun_maps, path = g1m_name+'/', e=e, cull_vertices = cull_vertices,\
                    transform_cloth = transform_cloth, write_empty_buffers = write_empty_buffers,\
                    preserve_trianglestrip = preserve_trianglestrip)
    return(True)
