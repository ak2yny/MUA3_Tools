# Based primarily off of:
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - https://github.com/eArmada8/gust_stuff
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# requirements
from enum import Enum
from numpy import frombuffer, fromiter, linalg, dtype, ndarray

# import pip
# pip.main(['install', 'pyquaternion', '--user'])
# from pyquaternion import Quaternion

# local
from .lib_gust import * # incl. endian config
from .lib_nun import NUNO1, NUNO3, NUNO5, NUNV1

# native
from dataclasses import InitVar, dataclass, field # astuple, 
from struct import calcsize, unpack_from


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
class G1MGHeader(GResourceHeader):
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
    # def __post_init__(self):
    #     if self.parentID == 0xFFFFFFFF: # root bone as absolute origin; if struct is i, use parentID < 0
    #         self.abs_tm = Quaternion(self.rotation).transformation_matrix
    #         self.abs_tm[3,:3] = self.position # or even (0.0, 0.0, 0.0)
    def to_matrix(self) -> ndarray:
        mat = None # Quaternion(self.rotation).transformation_matrix
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
    parentIDs: set[int]
    bIsInternal: bool

    def __init__(self, data: bytes, pos: int, version: int):
        """
        Read G1MS section, sans Gust header (G1MS magic, version, size)
        Raises an index out of range exception if jointCount is 0 (should be 1 if skeleton is external)
        """
        shs = calcsize(G1MS_HEADER_STRUCT)
        self.header = G1MSHeader(*unpack_from(E+G1MS_HEADER_STRUCT, data, pos + 12))
        self.joints = [G1MSJoint(*unpack_from(E+G1MS_JOINT_STRUCT, data, p)) for p in range(pos + self.header.jointInfoOffset, pos + self.header.jointInfoOffset + self.header.jointCount * 48, 48)]
        self.parentIDs = set(i.parentID for i in self.joints)
        if version < 0x30303332:
            # no global indices in early versions, it seems
            self.globalIDToLocalID = self.localIDToGlobalID = {i: i for i in range(self.header.jointCount)}
            self.bIsInternal = True
        else:
            # IMPORTANT: Joint index (enum val) equals localID
            self.globalIDToLocalID = self.localIDToGlobalID = {}
            for i, localID in enumerate(unpack_from(f'{E} {self.header.jointIndicesCount}H', data, pos + 12 + shs)):
                if not localID == 0xFFFF:
                    self.localIDToGlobalID[localID] = i
                    self.globalIDToLocalID[i] = localID
            self.bIsInternal = self.joints[0].parentID != 0x80000000

    def getName(self, localID: int, global_to_oid: dict = {}, prefix: str = 'bone_') -> str:
        globalID = self.localIDToGlobalID[localID ^ 0x80000000 if not self.bIsInternal and localID >> 31 else \
                                          self.findLocalID(localID)]
        return global_to_oid[globalID] if globalID in global_to_oid else f'{prefix}{globalID}'

    def findLocalID(self, localID: int) -> int:
        # WIP: Layering system not (yet) implemented
        while localID not in self.localIDToGlobalID and localID < 100000:
            localID += 10000
        return localID

    def findGlobalID(self, globalID: int) -> int:
        """Strip external reference part and access in globalIDToLocalID. Key not found exception."""
        return self.globalIDToLocalID[globalID ^ 0x80000000 if globalID >> 31 else globalID]

    def getJoint(self, globalID: int) -> G1MSJoint:
        return self.joints[self.findGlobalID(globalID)] # Note: Not confirmed for all referenced, but plausible

    def addJoint(self, joint: G1MSJoint, globalID: int = 0):
        """
        Add joint to self.joints, updating values
        joint must have correct abs_tm, as this calculation seems to be individual,
        it doesn't seem to make much sense to append it here.
        (calc_abs_rotation_position(joint, self.joints[joint.parentID]))
        """
        if not globalID:
            globalID = self.header.jointIndicesCount
            self.header.jointIndicesCount += 1
        localID = self.header.jointCount
        while localID in self.localIDToGlobalID:
            localID += 10000
        self.localIDToGlobalID[localID] = globalID
        self.globalIDToLocalID[globalID] = localID
        self.joints.append(joint)
        self.header.jointCount += 1

@dataclass
class G1MGJointPaletteEntry:
    G1MMIndex: int
    physicsIndex: int
    jointIndex: int
    def __post_init__(self):
        if self.jointIndex >> 31: # >= 0x80000000
            self.physicsIndex &= 0xFFFF # ^ 0x80000000
            self.jointIndex &= 0xFFFF

@dataclass
class G1MGJointPalette:
    jointCount: int
    joints: list[G1MGJointPaletteEntry]
    # jointMapBuilder: list = field(default_factory=list) # useless on a class with overridden init

    def __init__(self, data: bytes, pos: int): # , internalSkel: G1MS = None, externalSkel: G1MS = None, globalToFinal: dict = None
        self.jointCount, = unpack_from(E+'I', data, pos)
        self.joints = [G1MGJointPaletteEntry(*unpack_from(E+'3I', data, pos)) for pos in range(pos + 4, pos + 4 + self.jointCount * 12, 12)]
        """ Backup code. Not sure if this is useful
        if internalSkel:
            for entry in self.joints:
                self.jointMapBuilder.append(
                    globalToFinal[
                        internalSkel.localIDToGlobalID.get(entry.jointIndex ^ 0x80000000) if externalSkel and entry.jointIndex >> 31 else \
                        externalSkel.localIDToGlobalID.get(entry.jointIndex) if externalSkel else \
                        internalSkel.localIDToGlobalID.get(entry.jointIndex)
                    ]
                )
        """

# =================================================================
# VertexSpecs and Spec classes, used to store all attributes and values
# =================================================================

G1MG_VERTEXATTRIBUTE_STRUCT = '2H4B'
GVA_SZ = calcsize(G1MG_VERTEXATTRIBUTE_STRUCT)

@dataclass
class G1MGVertexAttribute:
    bufferID: int
    offset: int
    dataType: int # typeHandler: int
    dummyVar: int
    semantic: int|str # attribute: int
    layer: int

    def __post_init__(self):
        # Raises index out of range if not supported
        self.semantic = GLTF_Semantic[self.semantic]
    # if self.dataType not in G1MGVAStructType: self.dataType = 0xFF
    # self.dataType = G1MGVAStructType[self.dataType]
    # self.bufferID = vBufferIndices[self.bufferID]


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

@dataclass
class G1MGVertexBuffer:
    unknown1: int
    stride: int
    count: int
    unknown2: int = 0
    offset: int = 0

class G1MGIndexBuffer:
    count: int
    dataType: int
    unknown1: int
    offset: int
    bitwidth: int
    npDataType: dtype
    glTF_typ: str
    glTF_acc: int

    def __init__(self, data: bytes, pos: int, version: int):
        self.count, self.dataType, unk1 = unpack_from(E+'3I', data, pos)
        self.offset = pos + 8
        if version > 0x30303430: # old versions don't have this
            self.unknown1 = unk1
            self.offset += 4
        self.bitwidth = self.dataType // 8
        self.npDataType = dtype(f'uint{self.dataType}')
        self.glTF_typ = 'SCALAR'
        # Unsigned, for signed, remove +1
        self.glTF_acc = 0 if self.dataType == 64 else 5120 + self.dataType // 16 * 2 + 1

    # def to_bytes(self) -> bytes:
    #     attr = (self.count, self.dataType)
    #     if hasattr(self, 'unknown1'): attr += (self.unknown1,)
    #     return pack(f'{E} {len(attr)}I', *attr)

""" Enum alts
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

GLTF_Semantic = (
    'POSITION',
    'WEIGHTS', # JointWeight
    'JOINTS', # JointIndex
    'NORMAL',
    'PSIZE',
    'TEXCOORD', # UV
    'TANGENT',
    'BINORMAL',
    'TESSFACTOR', # TessalationFactor
    'POSITIONT', # PosTransform
    'COLOR',
    'FOG',
    'DEPTH',
    'SAMPLE'
)

class G1MGVAFormat(Enum):
    FLOAT32x1 = 0x00, 'f', 4, 1, 'SCALAR', 5126 
    FLOAT32x2 = 0x01, 'f', 4, 2, 'VEC2',   5126 
    FLOAT32x3 = 0x02, 'f', 4, 3, 'VEC3',   5126 
    FLOAT32x4 = 0x03, 'f', 4, 4, 'VEC4',   5126 
    UINT8x4   = 0x05, 'B', 1, 4, 'VEC4',   5121 
    UINT16x4  = 0x07, 'H', 2, 4, 'VEC4',   5123 
    UINT32x4  = 0x09, 'I', 4, 4, 'VEC4',   5125 # Need confirmation
    FLOAT16x2 = 0x0A, 'e', 2, 2, '', 0 
    FLOAT16x4 = 0x0B, 'e', 2, 4, '', 0 
    UNORM8x4  = 0x0D, 'B', 1, 4, '', 0 
    UNKNOWN   = 0xFF, 'I', 4, 1, 'SCALAR', 5125 
    def __new__(cls, value: int, char: str, byte_count: int, size: int, glTF_typ: str, glTF_acc: int):
        member = object.__new__(cls)
        member._value_ = value
        member.dtype = E+char
        member.byte_count = byte_count
        member.size = size
        member.glTF_typ = glTF_typ
        member.glTF_acc = glTF_acc
        return member
    @classmethod
    def _missing_(cls, value):
        new = cls.UNKNOWN
        new._value_ = value
        return new
    def read(self, data: bytes, vb: G1MGVertexBuffer, ao: int) -> ndarray:
        """Read and return bytes as np.array, according to the G1MGVAFormat and G1MGVertexBuffer, and return the array from offset ao."""
        esz = vb.stride // self.byte_count
        if self == G1MGVAFormat.UNORM8x4:
            return (frombuffer(data, self.dtype, count=vb.count * esz, offset=vb.offset) / 255.0).reshape(vb.count, esz)[:,ao:ao + self.size]
        return frombuffer(data, self.dtype, count=vb.count * esz, offset=vb.offset).reshape(vb.count, esz)[:,ao:ao + self.size]
    def write(self, data: iter) -> bytes:
        """Write a any flat iterable to bytes, according to the G1MGVAFormat and endian."""
        # WIP: Must be one dimensional and it's unknown as to how the bytes are written
        return fromiter(data, self.dtype).tobytes()

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
    externalID: int # NUNID (Seems to refer to NUN entries [NUNO1, etc.] with layers)
    indexCount: int
    data: InitVar[bytes]
    pos: InitVar[int]
    indices: tuple[int] = field(init=False)

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
class G1MG(G1MGHeader):
    # bounding_box: dict
    # meshCount: int # not (yet) used (?)
    data: InitVar[bytes]
    pos: InitVar[int]
    geometry_sockets: list = field(default_factory=list)
    materials: list[G1MGMaterial] = field(default_factory=list)
    shader_params: list = field(default_factory=list)
    vertex_buffers: list[G1MGVertexBuffer] = field(default_factory=list)
    vertexAttributeSets: list[G1MGVertexAttributeSet] = field(default_factory=list)
    joint_palettes: list[G1MGJointPalette] = field(default_factory=list)
    index_buffers: list[G1MGIndexBuffer] = field(default_factory=list)
    submeshes: list[G1MGSubmesh] = field(default_factory=list)
    meshGroups: list[G1MGMeshGroup] = field(default_factory=list) # mesh_lod
    # WIP: These list might have to be put in a single list with an id for each list entry, to preserve the order
    # meshInfo: list = []
    # boneMaps: list = []
    # boneMapListCloth: list = []
    # spec: list = []
    # texture: list = []

    def __post_init__(self, data: bytes, pos: int): # , internalSkel: G1MS = None, externalSkel: G1MS = None, globalToFinal: dict = None
        # Read headers (size hardcoded), WIP: could create the bounding_box on serialization
        # self.bounding_box = dict(list(self.__dict__.items())[5:11])
        self.magic = self.magic.decode()
        self.platform = self.platform.decode()
        sms = calcsize(G1MG_SUBMESH_STRUCT)
        pos += 12 + calcsize(G1MG_HEADER_STRUCT)
        for _ in range(self.sectionCount):
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
                        mat = G1MGMaterial(*unpack_from(E+'4I', data, pos))
                        pos += G1MG_MAT_SZ
                        mat.g1mgTextures = [G1MGTexture(*unpack_from(E+'6H', data, p)) for p in range(pos, pos + mat.textureCount * G1MG_TEX_SZ, G1MG_TEX_SZ)]
                        self.materials.append(mat)
                        pos += mat.textureCount * G1MG_TEX_SZ
                case 0x00010003:
                    for _ in range(section.count):
                        shader_info = []
                        pos += 4
                        for _ in range(unpack_from(E+'I', data, pos - 4)[0]):
                            shader = G1MGShader(data, pos)
                            shader_info.append(shader)
                            pos += shader.size
                        self.shader_params.append(shader_info)
                case 0x00010004:
                    for _ in range(section.count):
                        vs = 4 if self.chunkVersion > 0x30303430 else 3
                        vb = G1MGVertexBuffer(*unpack_from(f'{E} {vs}I', data, pos))
                        vb.offset = pos + vs * 4
                        self.vertex_buffers.append(vb)
                        pos += vs * 4 + vb.stride * vb.count
                case 0x00010005:
                    for _ in range(section.count):
                        va = G1MGVertexAttributeSet(data, pos)
                        self.vertexAttributeSets.append(va)
                        pos += 8 + 4 * va.indexCount + GVA_SZ * va.attributesCount
                case 0x00010006:
                    for _ in range(section.count):
                        jp = G1MGJointPalette(data, pos) # , internalSkel, externalSkel, globalToFinal
                        self.joint_palettes.append(jp)
                        pos += jp.jointCount * 12 + 4
                case 0x00010007:
                    for _ in range(section.count):
                        ib = G1MGIndexBuffer(data, pos, self.chunkVersion)
                        self.index_buffers.append(ib)
                        pos = ib.offset + ib.count * ib.bitwidth
                        pos += (4 - pos) % 4
                case 0x00010008:
                    end = pos + section.count * sms
                    self.submeshes = [G1MGSubmesh(*unpack_from(E+G1MG_SUBMESH_STRUCT, data, p)) for p in range(pos, end, sms)]
                    pos = end
                case 0x00010009:
                    for _ in range(section.count):
                        mg = G1MGMeshGroup(*unpack_from(E+G1MG_MESHGROUP_STRUCT, data, pos))
                        pos = mg.readMeshes(data, pos, self.chunkVersion)
                        self.meshGroups.append(mg)
                # case _:
                #   self.unknown.append('UNKNOWN')
            pos = end

    def get_vb(self, submesh_vb_index: int, semantic: str, data: bytes, layer_threshold: int = -1):
        """Get the buffer for the submesh and semantic. Raises index out of range exception if index too high.
        WIP: Change to numpy return data_type.read(data, vb.count * vb.stride, vb.offset + a.offset)
        """
        # if submesh_vb_index < len(self.vertexAttributeSets)
        for a in self.vertexAttributeSets[submesh_vb_index].attributes:
            if a.semantic == semantic and a.layer > layer_threshold:
                data_type = G1MGVAFormat(a.dataType)
                # Since vBufferIndices seem to correspond with the list indices [0, 1, 2, ...], we could possibly use self.vertex_buffers[a.bufferID]
                vb = self.vertex_buffers[self.vertexAttributeSets[submesh_vb_index].vBufferIndices[a.bufferID]]
                # Note: This is usually the same buffer, but G1MGVertexAttribute.offset gets the current part.
                fmt = f'{E} {data_type.size}{data_type.dtype[1]}'
                return (unpack_from(fmt, data, p) for p in range(vb.offset + a.offset, vb.offset + a.offset + vb.count * vb.stride, vb.stride))
                # WIP: if cull_vertices: return [vb[i] for i in si.keys()] # see cull_vb
        return iter(())


"""
# =================================================================
# Matrix data
# =================================================================

@dataclass
class G1MM:
    matrixCount: int
    matrices: bytes
    def __init__(self, data: bytes, pos: int):
        ""
        Read G1MM section, sans Gust header (G1MM magic, version, size)
        Header size = 12
        WIP: Needs to be converted
        ""
        self.matrixCount, = unpack_from(E+'I', data, pos + 12)
        self.matrices = data[pos + 16:pos + 16 + self.matrixCount * 64]

"""

# =================================================================
# Skeleton Functions
# =================================================================

def calc_abs_rotation_position(bone: G1MSJoint, parent_bone: G1MSJoint) -> ndarray:
    """
    Takes quat/pos relative to parent, and reorients / moves to be relative to the origin.
    Parent bone must already be transformed.
    WIP: This should probably be calculated when used (but Keep)
    """
    q1 = None # Quaternion(bone.rotation)
    qp = None # Quaternion(matrix=parent_bone.abs_tm)
    abs_tm = (qp * q1).unit.transformation_matrix
    abs_tm[3,:3] = (qp.rotate(bone.position) + parent_bone.abs_tm[3,:3])
    return abs_tm

""" Unused
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
"""

# =================================================================
# NUN, Cloth, Physique Functions
# =================================================================

def make_nun_bones(nun: NUNO1|NUNO3|NUNO5|NUNV1, skel: G1MS) -> list[G1MSJoint]:
    """Build a nun skeleton, parented to the nun parent bone. May fail (index out of range exception)."""
    nun_bones: list[G1MSJoint] = []
    parent_joint = skel.getJoint(nun.parentBoneID)
    for pointIndex, cp in enumerate(nun.controlPoints):
        link = nun.influences[pointIndex] # cp and influences have an identical count
        if link.P3 == -1:
            parentID = skel.findGlobalID(nun.parentBoneID)
            q = None # Quaternion()
            p = cp[:3] # cp are 3 or 4 floats
        else:
            parentID = link.P3
            t = nun_bones[link.P3].abs_tm
            qpi = None # Quaternion(matrix=t).inverse
            t[:3,3] = t[3,:3]
            q = None # Quaternion(matrix=parent_joint.abs_tm) * qpi
            p = linalg.inv(t)[:3,3] + q.rotate(cp[:3]) + qpi.rotate(parent_joint.abs_tm[3,:3])
            parent_joint = nun_bones[link.P3]
        bone = G1MSJoint(
            1.0, 1.0, 1.0,
            parentID,
            *q.vector, q[0]
            *p, 0.0)
        bone.abs_tm = calc_abs_rotation_position(bone, parent_joint)
        nun_bones.append(bone)
    return nun_bones

def compute_center_of_mass(position: tuple, weights: tuple, bones_indices: tuple[int], nun_bones: list[G1MSJoint]):
    # nun_bones must correspond with the control points and have abs_tm already
    # WIP: Names seem not chosen well (for this use) | position is always 0, 0, 0?
    temp = ndarray(3)
    for bone_num, bone_idx in enumerate(bones_indices):
        tm = nun_bones[bone_idx].abs_tm
        temp += None # Quaternion(matrix=tm).rotate(position) + tm[3,:3] * weights[bone_num]
    return temp

""" Unused:
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

def find_submeshes(subvbs: list[G1MGSubmesh]):
    ""
    Build a quick dictionary of the meshes, each with a list of submesh indices.
    This enables subvbs[vbsubs[vertexBufferIndex][0]] instead of next(s for s in subvbs if s.vertexBufferIndex == vertexBufferIndex).
    ""
    # The by mesh and submesh loop from ProjectG1M probably works better
    vbsubs = {x: [] for x in {s.vertexBufferIndex for s in subvbs}}
    for i, s in enumerate(subvbs):
        vbsubs[s.vertexBufferIndex].append(i)
    return vbsubs

def generate_ib(data: bytes, ib: G1MGIndexBuffer, submesh: G1MGSubmesh):
    ""Read the index buffer bytes in a tuple.""
    ib = unpack_from(f'{E} {ib.count * ib.dataType}', data, ib.offset)
    if submesh.indexBufferPrimType == 4: # and preserve_trianglestrip == False: # (1 prim, 3 triangle, 4 trianglestrip)
        return [x for i in range(0, len(ib) - 2, 2)
              for x in ((ib[i], ib[i + 1], ib[i + 2]),
                        (ib[i + 1], ib[i + 3], ib[i + 2]))]
    else:
        # Turn (back) into 2D list so cull_vertices works
        return [(x,) for x in ib]

# Alternative ways to parse in certain ways:
# ib.dataType should always be a single int (B, H, I):
# return unpack_from(f'{E} {ib.count}{ib.dataType}', data, ib.offset)
# return [unpack_from(E+ib.dataType, data, p) for p in range(ib.offset, ib.offset + ib.bitwidth * ib.count, ib.bitwidth)]
# tuples of three (triangles):
# return [unpack_from(f'{E} 3{ib.dataType}', data, p) for p in range(ib.offset, ib.offset + ib.bitwidth * ib.count, ib.bitwidth * 3)]

def cull_vb(ib: tuple[tuple], vb: list[tuple]) -> dict:
    ""
    Cull a vertex buffer according to the index buffer as sorted set (keeping only referenced vertices).
    The index buffer is updated with the new reference (WIP: should only be done once in advance)
    ""
    # ib must be 2 dimensional
    si = {oi: i for i, oi in enumerate(sorted({x for l in ib for x in l if i < len(vb)}))}
    vb = [vb[i] for i in si.keys()]
    for i, ibe in enumerate(ib):
        for j, idx in enumerate(ibe):
            ib[i][j] = si[idx]
    return vb, ib

def generate_vgmap(boneindex: int, g1mg: G1MG, skel_data: G1MS):
    ""WIP: Unknown if useful""
    # WIP: return {skel_data.getGlobalID(j.jointIndex): i * 3 for i, j in enumerate(g1mg.joint_palettes[boneindex].joints)}
    if skel_data.header.jointCount < 2: return # WIP
    return {skel_data.localIDToGlobalID[j.jointIndex ^ 0x80000000 if not skel_data.bIsInternal and j.jointIndex >> 31 else \
                                        j.jointIndex]: i * 3
               for i, j in enumerate(g1mg.joint_palettes[boneindex].joints)
           } # f'bone_{skel_data.localIDToGlobalID[j.jointIndex]}' = i * 3
"""
