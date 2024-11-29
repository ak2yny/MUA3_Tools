# Based primarily off of:
#   - https://github.com/VitaSmith/gust_tools
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai, DarkstarSword and others
# Many thanks to them, as well as eArmada8, https://github.com/eterniti/g1m_export (& vagonumero13).

# native
import json
from dataclasses import astuple, InitVar, dataclass, field
from enum import Enum
from math import log2
from pathlib import Path
from struct import calcsize, pack, unpack, unpack_from

# local
from lib.lib_gust import * # incl. endian config
from MUA3_ZL import backup


# WIP: I'm not sure if DDS endian is important


# =================================================================
# Format Helpers
# =================================================================

"""
EG1TASTCFormat = { # mostly guessed
    0x0: 'ASTC_4_4', # Confirmed
    0x1: 'ASTC_5_4',
    0x2: 'ASTC_5_5',
    0x3: 'ASTC_6_5',
    0x4: 'ASTC_6_6',
    0x5: 'ASTC_8_5',
    0x6: 'ASTC_8_6',
    0x7: 'ASTC_8_8', # Confirmed
    0x8: 'ASTC_10_5',
    0x9: 'ASTC_10_6',
    0xA: 'ASTC_10_8',
    0xB: 'ASTC_10_10',
    0xC: 'ASTC_12_10',
    0xD: 'ASTC_12_12'
}

G1T_ASTCEXTRAINFO_STRUCT = '2H2BH'

@dataclass
class G1TASTCExtraInfo:
    unk0: int
    unk1: int
    Format: int # EG1TASTCFormat
    unk2: int
    unk3: int

class D3D10_RESOURCE_DIMENSION:
    UNKNOWN = 0
    BUFFER = 1
    TEXTURE1D = 2
    TEXTURE2D = 3
    TEXTURE3D = 4

bNormalized = True
bSpecialCaseETC = b3DSAlpha = bNeedsX360EndianSwap = False
rawFormat = ''
fourccFormat = originalSize = expected_texture_size = -1
mortonWidth = pvrtcBpp = 0
match texHeader.textureFormat:
    case 0x0:
        rawFormat = 'r8g8b8a8'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x1:
        rawFormat = 'b8g8r8a8'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x2:
        rawFormat = 'r32'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x3:
        rawFormat = 'r16g16b16a16'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x4:
        rawFormat = 'r32g32b32a32'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x6:
        fourccFormat = 'FOURCC_DXT1'
        bNeedsX360EndianSwap = True
    case 0x7:
        fourccFormat = 'FOURCC_DXT3'
    case 0x8:
        fourccFormat = 'FOURCC_DXT5'
    case 0xA:
        rawFormat = 'b8g8r8a8'
        expected_texture_size = texHeader.width * texHeader.height * 4
        mortonWidth = 0x20
    case 0xB:
        rawFormat = 'r32'
        expected_texture_size = texHeader.width * texHeader.height
    case 0xD:
        rawFormat = 'r32g32b32a32'
        expected_texture_size = texHeader.width * texHeader.height
    case 0xF:
        rawFormat = 'a8'
        expected_texture_size = texHeader.width * texHeader.height
    case 0x10:
        fourccFormat = 'FOURCC_DXT1'
        mortonWidth = 0x4
    case 0x12:
        fourccFormat = 'FOURCC_DXT5'
        mortonWidth = 0x8
    case 0x34:
        rawFormat = 'b5g6r5'
        expected_texture_size = texHeader.width * texHeader.height * 2
    case 0x35:
        expected_texture_size = texHeader.width * texHeader.height * 2
        rawFormat = 'a1b5g5r5'
    case 0x36:
        rawFormat = 'a4b4g4r4'
        expected_texture_size = texHeader.width * texHeader.height * 2
    case 0x3C:
        fourccFormat = 'FOURCC_DXT1'
    case 0x3D:
        fourccFormat = 'FOURCC_DXT1'
    case 0x47:
        rawFormat = '3DS_rgb'
        expected_texture_size = texHeader.width * texHeader.height * 4
    case 0x48:
        rawFormat = '3DS_rgb'
        expected_texture_size = texHeader.width * texHeader.height * 4
        b3DSAlpha = True
    case 0x56:
        rawFormat = 'ETC1_rgb'
        expected_texture_size = texHeader.width * texHeader.height / 2
    case 0x57:
        rawFormat = 'PVRTC'
        expected_texture_size = texHeader.width * texHeader.height / 4
        pvrtcBpp = 2
    case 0x58:
        expected_texture_size = texHeader.width * texHeader.height / 2
        rawFormat = 'PVRTC'
        pvrtcBpp = 4
    case 0x59:
        fourccFormat = 'FOURCC_DXT1'
    case 0x5B:
        fourccFormat = 'FOURCC_DXT5'
    case 0x5C:
        fourccFormat = 'FOURCC_ATI1'
        bNormalized = False
    case 0x5D:
        fourccFormat = 'FOURCC_ATI2'
        bNormalized = False
    case 0x5E:
        fourccFormat = 'FOURCC_BC6H'
        bNormalized = False
    case 0x5F:
        fourccFormat = 'FOURCC_BC7'
        bNormalized = False
    case 0x60:
        fourccFormat = 'FOURCC_DXT1'
        mortonWidth = 0x4
    case 0x62:
        fourccFormat = 'FOURCC_DXT5'
        mortonWidth = 0x8
    case 0x63:
        fourccFormat = 'FOURCC_BC4'
        mortonWidth = 0x4
        bNormalized = False
    case 0x64:
        fourccFormat = 'FOURCC_BC5'
        mortonWidth = 0x8
        bNormalized = False
    case 0x65:
        fourccFormat = 'FOURCC_BC6H'
        mortonWidth = 0x8
        bNormalized = False
    case 0x66:
        fourccFormat = 'FOURCC_BC7'
        mortonWidth = 0x8
        bNormalized = False
    case 0x6F:
        rawFormat = 'ETC1_rgb'
        expected_texture_size = texHeader.width * texHeader.height
        bSpecialCaseETC = True
        originalSize = expected_texture_size
        # WIP: could probably use better math
        for _ in range(1, texHeader.mip_count):
            # Mipmap size, skip the first entry which is the full-sized texture
            originalSize //= 4
            expected_texture_size += originalSize
        texHeader.height *= 2
        if not2ndToLast:
            hdr.offsetList[i + 1] = hdr.offsetList[i] + texHeader.headerSize + expected_texture_size
    case 0x71:
        rawFormat = 'ETC1_rgba'
        expected_texture_size = texHeader.width * texHeader.height
    case 0x7D:
        rawFormat = 'ASTC'

"""

class DDS_FORMAT(Enum):
    UNKNOWN = 0
    ABGR4 = 1
    ARGB4 = 2
    GRAB4 = 3
    RGBA4 = 4
    ABGR8 = 5
    ARGB8 = 6
    GRAB8 = 7
    RGBA8 = 8
    ARGB16 = 9
    ARGB32 = 10
    RXGB8 = 11
    BGR8 = 12
    R8 = 13
    UVER = 14
    DXT1 = 15
    DXT2 = 16
    DXT3 = 17
    DXT4 = 18
    DXT5 = 19
    DX10 = 20
    BC4 = 21
    BC5 = 22
    BC6 = 23
    BC7 = 24
    BC6H = 25
    BC7L = 26 # BC7L is unsupported?
    ATI1 = 27
    ATI2 = 28
    A2XY = 29
    DDS = 30
    NVTT = 31
    @property
    def dds_bwh(self) -> int:
        return 4 if self.value in (*range(15, 26), 27, 28) else \
               1
    @property
    def dds_bpb(self) -> int:
        return int(self._name_[4:]) // 2 if self.value in range(1, 12) else \
               3 if self.value == 12 else \
               1 if self.value == 13 else \
               8 if self.value in (15, 21, 27) else \
               16 if self.value in (*range(16, 26), 28) else \
               -1
    @property
    def dds_bpp(self) -> int:
        """ Alt. Way:
        fs = groupby(self._name_, key=str.isdigit)
        fmt = ''.join(next(fs)[1])
        """
        i = 4 if self.value in range(1, 12) else \
            3 if self.value == 12 else \
            1 if self.value == 13 else 0
        return int(self._name_[i:]) * len(self._name_[:i]) if i else \
               4 if self.value in (15, 21, 27) else \
               8 if self.value in (*range(16, 26), 28) else \
               -1
    @property
    def fourCC(self) -> int:
        if self.value < 14 and not self.value == 11:
            return -1
        fmt = 'ATI1' if self == DDS_FORMAT.BC4 else \
              'DX10' if self == DDS_FORMAT.BC7 else \
              self._name_[:4].ljust(4)
        return int(f'0x{fmt[::-1].encode().hex()}', 16)

TEXTURE_TYPE_TO_DDS_FORMAT = {
    # 0x00: # ???
    # 0x01: # ???
    # 0x02: # ???
    0x03: DDS_FORMAT.ARGB16,
    0x04: DDS_FORMAT.ARGB32,
    # PS Systems
    0x06: DDS_FORMAT.DXT1, # PS2??, PS3
    0x07: DDS_FORMAT.DXT3,
    0x08: DDS_FORMAT.DXT5, # PS3
    0x09: DDS_FORMAT.GRAB8, # PS4, swizzled
    # 0x0A: b8g8r8a8 # swizzled
    # 0x0B: r32
    # 0x0D: r32g32b32a32
    # 0x0F: a8
    # PSV, swizzled
    0x10: DDS_FORMAT.DXT1,
    0x11: DDS_FORMAT.DXT3,
    0x12: DDS_FORMAT.DXT5,
    # Switch
    0x21: DDS_FORMAT.ARGB8,
    # 0x34: b5g6r5
    # 0x35: a1b5g5r5
    # 0x36: a4b4g4r4
    # 3DS: 0x3C and 0x3D are definitely 16bpp, but after that...
    0x3C: DDS_FORMAT.ARGB4, # DXT1 fourCC
    0x3D: DDS_FORMAT.ARGB4, # DXT1 fourCC
    0x45: DDS_FORMAT.BGR8, # swizzled
    # 0x47: 3DS_rgb,
    # 0x48: 3DS_rgb,
    # 0x56: ETC1_rgb,
    # 0x57: PVRTC,
    # 0x58: PVRTC,
    # Win
    0x59: DDS_FORMAT.DXT1,
    0x5A: DDS_FORMAT.DXT3,
    0x5B: DDS_FORMAT.DXT5,
    0x5C: DDS_FORMAT.BC4, # ATI1?
    # 0x5D: DDS_FORMAT.ATI2,
    0x5E: DDS_FORMAT.BC6H,
    0x5F: DDS_FORMAT.BC7,
    # PS4, swizzled
    0x60: DDS_FORMAT.DXT1,
    0x61: DDS_FORMAT.DXT3,
    0x62: DDS_FORMAT.DXT5,
    0x63: DDS_FORMAT.BC4,
    0x64: DDS_FORMAT.BC5, # or BC6H?
    0x65: DDS_FORMAT.BC6,
    0x66: DDS_FORMAT.BC7,
    # 0x6F: ETC1_rgb, but very special
    # 0x71: ETC1_rgba,
    0x72: DDS_FORMAT.BC7, # Not actually BC7, but that's the closest we get to semi-recognizable output
    # 0x7D: ASTC,
}

SWIZZLED = (0x09, 0x0A, 0x10, 0x11, 0x12, 0x45,
            0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66)

class DXGI_FORMAT(Enum):
    UNKNOWN = 0
    R32G32B32A32_TYPELESS = 1
    R32G32B32A32_FLOAT = 2
    R32G32B32A32_UINT = 3
    R32G32B32A32_SINT = 4
    R32G32B32_TYPELESS = 5
    R32G32B32_FLOAT = 6
    R32G32B32_UINT = 7
    R32G32B32_SINT = 8
    R16G16B16A16_TYPELESS = 9
    R16G16B16A16_FLOAT = 10
    R16G16B16A16_UNORM = 11
    R16G16B16A16_UINT = 12
    R16G16B16A16_SNORM = 13
    R16G16B16A16_SINT = 14
    R32G32_TYPELESS = 15
    R32G32_FLOAT = 16
    R32G32_UINT = 17
    R32G32_SINT = 18
    R32G8X24_TYPELESS = 19
    D32_FLOAT_S8X24_UINT = 20
    R32_FLOAT_X8X24_TYPELESS = 21
    X32_TYPELESS_G8X24_UINT = 22
    R10G10B10A2_TYPELESS = 23
    R10G10B10A2_UNORM = 24
    R10G10B10A2_UINT = 25
    R11G11B10_FLOAT = 26
    R8G8B8A8_TYPELESS = 27
    R8G8B8A8_UNORM = 28
    R8G8B8A8_UNORM_SRGB = 29
    R8G8B8A8_UINT = 30
    R8G8B8A8_SNORM = 31
    R8G8B8A8_SINT = 32
    R16G16_TYPELESS = 33
    R16G16_FLOAT = 34
    R16G16_UNORM = 35
    R16G16_UINT = 36
    R16G16_SNORM = 37
    R16G16_SINT = 38
    R32_TYPELESS = 39
    D32_FLOAT = 40
    R32_FLOAT = 41
    R32_UINT = 42
    R32_SINT = 43
    R24G8_TYPELESS = 44
    D24_UNORM_S8_UINT = 45
    R24_UNORM_X8_TYPELESS = 46
    X24_TYPELESS_G8_UINT = 47
    R8G8_TYPELESS = 48
    R8G8_UNORM = 49
    R8G8_UINT = 50
    R8G8_SNORM = 51
    R8G8_SINT = 52
    R16_TYPELESS = 53
    R16_FLOAT = 54
    D16_UNORM = 55
    R16_UNORM = 56
    R16_UINT = 57
    R16_SNORM = 58
    R16_SINT = 59
    R8_TYPELESS = 60
    R8_UNORM = 61
    R8_UINT = 62
    R8_SNORM = 63
    R8_SINT = 64
    A8_UNORM = 65
    R1_UNORM = 66
    R9G9B9E5_SHAREDEXP = 67
    R8G8_B8G8_UNORM = 68
    G8R8_G8B8_UNORM = 69
    BC1_TYPELESS = 70
    BC1_UNORM = 71
    BC1_UNORM_SRGB = 72
    BC2_TYPELESS = 73
    BC2_UNORM = 74
    BC2_UNORM_SRGB = 75
    BC3_TYPELESS = 76
    BC3_UNORM = 77
    BC3_UNORM_SRGB = 78
    BC4_TYPELESS = 79
    BC4_UNORM = 80
    BC4_SNORM = 81
    BC5_TYPELESS = 82
    BC5_UNORM = 83
    BC5_SNORM = 84
    B5G6R5_UNORM = 85
    B5G5R5A1_UNORM = 86
    B8G8R8A8_UNORM = 87
    B8G8R8X8_UNORM = 88
    R10G10B10_XR_BIAS_A2_UNORM = 89
    B8G8R8A8_TYPELESS = 90
    B8G8R8A8_UNORM_SRGB = 91
    B8G8R8X8_TYPELESS = 92
    B8G8R8X8_UNORM_SRGB = 93
    BC6H_TYPELESS = 94
    BC6H_UF16 = 95
    BC6H_SF16 = 96
    BC7_TYPELESS = 97
    BC7_UNORM = 98
    BC7_UNORM_SRGB = 99
    AYUV = 100
    Y410 = 101
    Y416 = 102
    NV12 = 103
    P010 = 104
    P016 = 105
    _420_OPAQUE = 106
    YUY2 = 107
    Y210 = 108
    Y216 = 109
    NV11 = 110
    AI44 = 111
    IA44 = 112
    P8 = 113
    A8P8 = 114
    B4G4R4A4_UNORM = 115
    P208 = 116
    V208 = 117
    V408 = 118
    FORCE_UINT = 119

# =================================================================
# Flags, WIP: Some might not need to be an enumerable
# =================================================================

G1T_FLAG1_DOUBLE_HEIGHT  = 0x10 # Some textures need to be doubled in height
G1T_FLAG3_STANDARD_FLAGS = 0x01 # Flags that are commonly set
G1T_FLAG4_STANDARD_FLAGS = 0x12 # Flags that are commonly set
G1T_FLAG4_SRGB           = 0x20 # Set if the texture uses sRGB (unk4)
G1T_FLAG5_EXTENDED_DATA  = 0x01 # Set if the texture has local data in the texture entry.
class G1T_FLAG(Enum):
    NORMAL_MAP     = 0x00000003 # Usually set for normal maps (but not always)
    SURFACE_TEX    = 0x00000001 # Set for textures that appear on a model's surface (or G1T_FLAG5_EXTENDED_DATA??)
    TEXTURE_ARRAY  = 0xF00F0000

class D3D11_RESOURCE_MISC_FLAG(Enum):
    GENERATE_MIPS = 0x1
    SHARED = 0x2
    TEXTURECUBE = 0x4
    DRAWINDIRECT_ARGS = 0x10
    BUFFER_ALLOW_RAW_VIEWS = 0x20
    BUFFER_STRUCTURED = 0x40
    RESOURCE_CLAMP = 0x80
    SHARED_KEYEDMUTEX = 0x100
    GDI_COMPATIBLE = 0x200
    SHARED_NTHANDLE = 0x800
    RESTRICTED_CONTENT = 0x1000
    RESTRICT_SHARED_RESOURCE = 0x2000
    RESTRICT_SHARED_RESOURCE_DRIVER = 0x4000
    GUARDED = 0x8000
    TILE_POOL = 0x20000
    TILED = 0x40000
    HW_PROTECTED = 0x80000
    SHARED_DISPLAYABLE = 0x100000
    SHARED_EXCLUSIVE_WRITER = 0x200000

class DDPF(Enum):
    ALPHAPIXELS     = 0x00000001
    ALPHA           = 0x00000002
    FOURCC          = 0x00000004
    PALETTEINDEXED4 = 0x00000008 # PAL4
    PALETTEINDEXED8 = 0x00000020 # PAL8
    RGB             = 0x00000040
    PALETTEINDEXED1 = 0x00000800 # PAL1
    PALETTEINDEXED2 = 0x00001000 # PAL2
    ALPHAPREMULT    = 0x00008000 # PREMULTALPHA
    LUMINANCE       = 0x00020000
    # DDS_RGBA        = 0x00000041  # DDPF_RGB | DDPF_ALPHAPIXELS
    # DDS_LUMINANCEA  = 0x00020001  # DDPF_LUMINANCE | DDPF_ALPHAPIXELS
    # Custom NVTT flags:
    SRGB            = 0x40000000
    NORMAL          = 0x80000000

class DDS_HEADER_FLAGS(Enum):
    TEXTURE    = 0x00001007 # DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    MIPMAP     = 0x00020000 # DDSD_MIPMAPCOUNT
    VOLUME     = 0x00800000 # DDSD_DEPTH
    PITCH      = 0x00000008 # DDSD_PITCH
    LINEARSIZE = 0x00080000 # DDSD_LINEARSIZE
    # DDS_HEIGHT = 0x00000002 # DDSD_HEIGHT
    # DDS_WIDTH  = 0x00000004 # DDSD_WIDTH

class DDSCAPS(Enum):
    COMPLEX    = 0x00000008 # DDSCAPS_COMPLEX
    TEXTURE    = 0x00001000 # DDSCAPS_TEXTURE
    MIPMAP     = 0x00400000 # DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    MIPMAPCUBE = 0x00400008 # DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    # DDS_FLAGS_VOLUME = 0x00200000  # DDSCAPS2_VOLUME

class DDSCAPS2(Enum):
    CUBEMAP           = 0x00000200
    CUBEMAP_POSITIVEX = 0x00000400
    CUBEMAP_NEGATIVEX = 0x00000800
    CUBEMAP_POSITIVEY = 0x00001000
    CUBEMAP_NEGATIVEY = 0x00002000
    CUBEMAP_POSITIVEZ = 0x00004000
    CUBEMAP_NEGATIVEZ = 0x00008000
    ALLFACES          = 0x0000FE00
    """
    @property
    def ALLFACES(self) -> int:
        return (self.CUBEMAP_POSITIVEX.value |
                self.CUBEMAP_NEGATIVEX.value |
                self.CUBEMAP_POSITIVEY.value |
                self.CUBEMAP_NEGATIVEY.value |
                self.CUBEMAP_POSITIVEZ.value |
                self.CUBEMAP_NEGATIVEZ.value) | int(
                    self.CUBEMAP.value * 6 * 1.5)
    """


# =================================================================
# Headers
# =================================================================

G1T_HEADER_STRUCT = '4s6I'
G1T_TEXTUREINFO_STRUCT = '8B20s'
KHM_HEADER_STRUCT = '4s3I2H3f'
DDS_HEADER_STRUCT = '7I44s8I5I'
DDS_HEADER_DXT10_STRUCT = '5I'
G1T_HEADER_SZ = calcsize(G1T_HEADER_STRUCT)
G1T_HEADER_SZ = calcsize(G1T_HEADER_STRUCT)
DDS_HDXT10_SZ = calcsize(DDS_HEADER_DXT10_STRUCT)

@dataclass
class G1THeader(GResourceHeader):
    tableOffset: int # header_size
    textureCount: int
    platform: int
    ASTCExtraInfoSize: int

# WIP: try: f = DDS_FORMAT(f), return 4 except: return 1

@dataclass
class G1TTextureInfo:
    """
    Initialization variable extraData can be empty if extraHeaderVersion is 0,
    otherwise, it must be a byte string of exactly 20 bytes (use G1T_TEXTUREINFO_STRUCT).
    """
    mipSys: int # mipSys
    Type: int # textureFormat
    dxdy: int
    # mipmaps: int # subsys?, I or B?, actual mip_count??
    # dx: int
    # dy: int
    unk1: int
    unk2: int
    unk3: int
    unk4: int
    extraHeaderVersion: int

    extraData: InitVar[bytes]
    extraDataSize: int = field(init=False)
    depth: float = field(init=False)
    flags: int = field(init=False) # number of frames in a texture array + other flags (?)
    width: int = field(init=False)
    height: int = field(init=False)
    # headerSize: int = 0x8 + self.extraDataSize
    # bNormalized: bool = True
    # bSpecialCaseETC2: bool = False

    def __post_init__(self, extraData: bytes):
        # it seems like this must be 1 (01 in be and 10 in le), but always 0 if off
        # if E == '<': self.extraHeaderVersion >>= 4
        if self.extraHeaderVersion > 0:
            self.extraDataSize, self.depth, self.flags, w, h = unpack(E+'If3I', extraData)
            if self.extraDataSize > 12: self.width = w
            if self.extraDataSize > 16: self.height = h
    # WIP: dxdy or separate | same for set
    @property
    def dx_width(self) -> int:
        return 1 << (self.dxdy & 0xF if E == '<' else self.dxdy >> 4)
    @property
    def dy_height(self) -> int:
        return 1 << (self.dxdy >> 4 if E == '<' else self.dxdy & 0xF)
    @property
    def z_mipmaps(self) -> int:
        return self.mipSys & 0xF if E == '<' else self.mipSys >> 4
    @property
    def mip_count(self) -> int:
        return self.mipSys >> 4 if E == '<' else self.mipSys & 0xF

    @property
    def unk_as_single_flag(self) -> int:
        # Yep, it seems like only little endian needs to revert the 4bits
        # and the order of each flag byte seems to be the same
        return self.unk4 >> 4 | self.unk4 << 4 & 0x000000F0 | \
               self.unk3 << 4 & 0x00000F00 | self.unk3 << 12 & 0x0000F000 | \
               self.unk2 << 12 & 0x000F0000 | self.unk2 << 20 & 0x00F00000 | \
               self.unk1 << 20 & 0x0F000000 | self.unk1 << 28 & 0xF0000000 \
            if E == '<' else \
                self.unk4 | self.unk3 << 8 | self.unk2 << 16 | self.unk1 << 24

    def set_dxdx(self, width: int, heigh: int):
        """Set dimension values that are a power of two to the dxdx byte (8bit)."""
        self.dxdy = (width.bit_length() - 1) << 4 | (heigh.bit_length() - 1) if E == '<' else \
                    (heigh.bit_length() - 1) << 4 | (width.bit_length() - 1)
    def set_mipSys(self, mip_count: int, z_mipmaps: int):
        """Set 4bit values (0 to 15) to the mipSys byte (8bit)."""
        if mip_count < 16 and z_mipmaps < 16:
            self.mipSys = mip_count << 4 | z_mipmaps if E == '<' else \
                          z_mipmaps << 4 | mip_count

@dataclass
class KHMHeader:
    magic: str # GResourceHeader?
    version: int # GResourceHeader?
    unk: int # GResourceHeader?
    size: int
    width: int
    height: int
    floorLevel: float
    midLevel: float
    ceilingLevel: float

@dataclass
class DDS_HEADER:
    size: int
    flags: int
    height: int
    width: int
    pitchOrLinearSize: int
    depth: int
    mipMapCount: int
    reserved1: bytes
    # DDPIXELFORMAT:
    ddspf_size: int
    ddspf_flags: int
    ddspf_fourCC: int
    ddspf_RGBBitCount: int
    ddspf_RBitMask: int
    ddspf_GBitMask: int
    ddspf_BBitMask: int
    ddspf_ABitMask: int
    # DDCAPS2 (capabilities):
    caps: int
    caps2: int
    caps3: int # res
    caps4: int # res
    reserved2: int

@dataclass
class DDS_HEADER_DXT10:
    dxgiFormat: DXGI_FORMAT
    resourceDimension: int
    miscFlag: int
    arraySize: int
    miscFlags2: int
    def __post_init__(self):
        self.dxgiFormat = DXGI_FORMAT(self.dxgiFormat)

# =================================================================
# Platform
# =================================================================

class KNOWN_PLATFORMS(Enum):
    SONY_PS2 = 0x00
    SONY_PS3 = 0x01
    MICROSOFT_X360 = 0x02
    NINTENDO_WII = 0x03
    NINTENDO_DS = 0x04
    NINTENDO_3DS = 0x05
    SONY_PSV = 0x06
    GOOGLE_ANDROID = 0x07
    APPLE_IOS = 0x08
    NINTENDO_WIIU = 0x09
    MICROSOFT_WINDOWS = 0x0A
    SONY_PS4 = 0x0B
    MICROSOFT_XONE = 0x0C
    NINTENDO_SWITCH = 0x10
    @property
    def display_name(self) -> str:
        match self.value:
            case 0x00: return 'PS2'
            case 0x01: return 'PS3'
            case 0x02: return 'Xbox 360'
            case 0x03: return 'Wii'
            case 0x04: return 'DS'
            case 0x05: return '3DS'
            case 0x06: return 'Vita'
            case 0x07: return 'Android'
            case 0x08: return 'iOS'
            case 0x09: return 'WiiU'
            case 0x0A: return 'Windows'
            case 0x0B: return 'PS4'
            case 0x0C: return 'Xbox One'
            case 0x10: return 'Switch'

class UNKNOWN_PLATFORM:
    def __init__(self, platform: int):
       self.name = platform
       self.value = platform
       self.display_name = platform


# =================================================================
# Main Functions
# =================================================================

def show_info_head():
    print(f'TYPE OFFSET     SIZE       DIMENSIONS MIPMAPS PROPS NAME')

def g1t_to_dds(data: bytes, output_folder: Path, flip_image: bool): # unused options: list_only
    """Extract all textures in a .g1t file to the output_folder must make a backup first, this function doesn't."""
    hdr = G1THeader(*unpack_from(E+G1T_HEADER_STRUCT, data))
    version_string = pack('> I', hdr.chunkVersion).decode()
    if hdr.chunkSize != len(data):
        raise ValueError("File size mismatch.")
    if not hdr.chunkVersion or int(version_string, 16) > 0x2710:
        raise ValueError(f"Unexpected G1T version {version_string}.")
    if hdr.ASTCExtraInfoSize % 4:
        raise ValueError(f"Can't handle G1T files with global extra data that's not a multiple of 4.")
    if hdr.ASTCExtraInfoSize > 0xFFFF:
        raise ValueError(f"Can't handle G1T files with more than 64 KB of global extra data.")
    if hdr.chunkVersion >> 16 != 0x3030 and hdr.chunkVersion >> 16 != 0x3031:
        print(f'WARNING: Potentially unsupported G1T version {version_string}.')
    if output_folder.is_dir() and any(output_folder.iterdir()):
       backup(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    platform = KNOWN_PLATFORMS(hdr.platform) if hdr.platform in KNOWN_PLATFORMS else UNKNOWN_PLATFORM(hdr.platform)
    # Keep the information required to recreate the archive in a JSON file
    json_data = {
        'name': output_folder.stem,
        'version': version_string,
        'platform': platform.display_name,
        'flip': flip_image,
        'textures': [],
        'extra_data': unpack_from(f'{E} {hdr.ASTCExtraInfoSize // 2}H', data, hdr.tableOffset + hdr.textureCount * 4)
    }
    # if not flip_image: del json_data['flip']
    flag_table = unpack_from(f'{E} {hdr.textureCount}I', data, G1T_HEADER_SZ)
    offset_table = unpack_from(f'{E} {hdr.textureCount}I', data, hdr.tableOffset)
    # formatList = unpack_from(E+'4xB3x'*(header.ASTCExtraInfoSize//4), data, hdr.tableOffset + 4 * hdr.textureCount) !! size should probably be 8, though
    # ASTCExtraInfoList = [G1TASTCExtraInfo(*unpack_from(E+G1T_ASTCEXTRAINFO_STRUCT, data, pos + aeis * i)) for i in range(header.ASTCExtraInfoSize // 4)]

    default_texture_format = get_default_texture_format(platform)
    # show_info_head()

    for i, pos in enumerate(offset_table):
        texHeader = G1TTextureInfo(*unpack_from(E+G1T_TEXTUREINFO_STRUCT, data, hdr.tableOffset + pos))
        if texHeader.mip_count == 0:
            print(f'ERROR: {i:04d} not exported. Number of mipmaps is 0.')
            continue
        if texHeader.extraHeaderVersion > 0 and texHeader.extraDataSize not in (0x0c, 0x10, 0x14):
            print(f'ERROR: {i:04d} not exported. Extra data size of 0x{texHeader.extraDataSize:02x} not supported.')
            continue
        if texHeader.Type not in (0, 1, 2, 3, 4, 6, 8, 9, 16, 18, 33, 60, 61, 69, 89, 91, 92, 94, 95, 96, 98, 114):
            # Just to be on the safe side.
            print(f'ERROR: {i:04d} not exported. Texture type 0x{texHeader.Type:02x} not supported.')
            continue

        extended_data = texHeader.extraHeaderVersion > 0 and texHeader.extraDataSize > 0
        texture = {
            'name': f'{i:04d}.dds',
            'Type': texHeader.Type,
            'mipmaps': texHeader.mip_count,
            'z_mipmaps': texHeader.z_mipmaps, # might not be needed usually (as it's 0)
            'nb_frames': max((((texHeader.flags) >> 28) & 0x0F) + (((texHeader.flags) >> 12) & 0xF0), 1) if extended_data else 1,
            'depth': texHeader.depth if extended_data else 0.0,
            'flag': flag_table[i],
            'unknown_flags': (texHeader.unk1, texHeader.unk2, texHeader.unk3, texHeader.unk4),
            'extended_data': extended_data
        }
        if texture['mipmaps'] == 1: del texture['mipmaps'] # something seems to be wrong, DDS should match mip count of 1 if none?
        # Assumption: The main flag is never bigger than 0X00FFFFFF
        # This was only relevant in the original script, when inserting the unknown flag bytes
        # if flag_table[i] & 0xFF000000:
        #     print(f'{i:04d} not exported. Global flags (0x{flag_table[i]:08x}) exceed maximum size of 0x00FFFFFF.')
        #     continue
        width = texHeader.dx_width
        height = texHeader.dy_height
        if texHeader.unk1 & G1T_FLAG1_DOUBLE_HEIGHT:
            height *= 2
        if extended_data:
            texture['extended_data_flag'] = texHeader.flags
            if texHeader.extraDataSize > 0x0c:
                width = texHeader.width
            elif texHeader.extraDataSize > 0x10:
                height = texHeader.height

        tex_hdr_sz = 8
        if extended_data: tex_hdr_sz += texHeader.extraDataSize
        texture_format = TEXTURE_TYPE_TO_DDS_FORMAT[texHeader.Type] if texHeader.Type in TEXTURE_TYPE_TO_DDS_FORMAT else \
                         default_texture_format
        min_mipmap_size = 0x40 * texture_format.bpb if platform.display_name == 'NINTENDO_WIIU' else texture_format.dds_bpb
        expected_texture_size = sum(texture['nb_frames'] * max(mipmap_size(texture_format, l, width, height), min_mipmap_size) for l in range(texHeader.mip_count))
        texture_size = hdr.chunkSize - hdr.tableOffset - offset_table[i] - tex_hdr_sz if i + 1 == hdr.textureCount else \
                       (offset_table[i + 1] if i <= hdr.textureCount else hdr.chunkSize) - pos - tex_hdr_sz

        cubemap = False
        if texture_size < expected_texture_size:
            print(f'ERROR: {i:04d} not exported. Actual texture size is smaller than expected size.')
            continue
        elif texture_size > expected_texture_size:
            if texture_size % expected_texture_size != 0:
                print(f'WARNING: Actual texture size is larger than expected size by 0x{texture_size - expected_texture_size:x}.')
            elif texture_size // expected_texture_size == 6:
                # A cubemap is composed of one texture for each face
                # texture['extended_data_flag'] |= G1T_FLAG.CUBE_MAP WIP: Might have to change to flags if too many
                cubemap = True
            else:
                print(f'ERROR: {i:04d} not exported. Cube map factor of {texture_size / expected_texture_size} instead of 6.')
                continue
            # expected_texture_size = texture_size

        # print(f'0x{texHeader.Type:02x} 0x{hdr.tableOffset + offset_table[i]:08x} 0x{texture_size:08x} {f'{width}x{height}':<10} {texHeader.mip_count:<7} {'A' if texture['nb_frames'] > 1 else '-'}{'B' if E == '>' else '-'}{'C' if texture.get('cubemap', False) else '-'}{'D' if texture['depth'] != 0.0 else '-'}  {i:04d}.dds')
        # if list_only: continue

        bpp = texture_format.dds_bpp
        if bpp < 1:
            print(f'ERROR: Unsupported bits-per-pixel value {bpp}')
        json_data['textures'].append(texture)

        if (texHeader.Type in SWIZZLED or
            (texture_format.value in range(1, 9) and texture_format.name[:4] != 'ARGB') or
            flip_image):
            texture_data = bytearray(texture_data)

            if texture_format.value in range(1, 9) and texture_format.name[:4] != 'ARGB':
                dds_payload = rgba_convert(dds_payload, texture_format, 'ARGB')

            if texHeader.Type in SWIZZLED:
                morton_order = 3 if platform.name in ('SONY_PS4', 'NINTENDO_3DS') else \
                               1 if platform.name == 'NINTENDO_WIIU' else \
                               int(log2(min(width // texture_format.dds_bwh,
                                            height // texture_format.dds_bwh))) # WiiU: Same for all mipmaps
                assert morton_order != 0
                width_factor = 2 if platform.name in ('SONY_PS4', 'NINTENDO_3DS') else \
                               16 // texture_format.dds_bpb if platform.name == 'NINTENDO_WIIU' else \
                               1
                add_width_fa = 8 if platform.name == 'NINTENDO_WIIU' else \
                               1
                # WIP: Handle morton for texture arrays & cubemaps
                offset = 0
                for j in range(texHeader.mip_count):
                    msz = mipmap_size(texture_format, j, width, height)
                    mw = max(add_width_fa * texture_format.dds_bwh, width / (1 << j))
                    mh = max(add_width_fa * texture_format.dds_bwh, height / (1 << j))
                    if width / (1 << j) < mw:
                        texture_data[offset:offset + msz] = tiling(texture_format, width / (1 << j), mw, texture_data[offset:offset + msz], max(min_mipmap_size, msz), True)
                    texture_data[offset:offset + msz] = mortonize(texture_format, morton_order, mw, mh, texture_data[offset:offset + msz], max(msz, min_mipmap_size), width_factor)
                    offset += msz
                    if platform.name != 'NINTENDO_WIIU': morton_order += -1 if morton_order > 0 else 1
                    if morton_order == 0: break

            if flip_image:
                texture_data = flip_vertically(texture_format.dds_bpp, bytearray(texture_data), texture_size, width)

            # if platform.name == 'MICROSOFT_X360' and (bNeedsX360EndianSwap or width_factor > 0):
                # do nothing with the data (or should be untiledTexData)? '> H'
        else:
            texture_data = None

        extra_flags = getattr(texHeader, 'flags', 0)
        use_dx10 = (texture_format in (DDS_FORMAT.BC7, DDS_FORMAT.DX10) or
                    texHeader.unk4 & G1T_FLAG4_SRGB or
                    extra_flags & G1T_FLAG.TEXTURE_ARRAY.value) and (
                    texHeader not in (DDS_FORMAT.ARGB16, DDS_FORMAT.ARGB32))

        dds_header = DDS_HEADER(
            size=124,
            flags=DDS_HEADER_FLAGS.TEXTURE.value | DDS_HEADER_FLAGS.LINEARSIZE.value, # or DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT instead of TEXTURE
            height=height,
            width=width,
            pitchOrLinearSize=width * height * texture_format.dds_bpb if texture_format.dds_bpb < 8 else ((width + 3) // 4) * ((height + 3) // 4) * texture_format.dds_bpb,
            depth=0, # hardcoded
            mipMapCount=texHeader.mip_count,
            reserved1=bytes(4 * 11),
            ddspf_size=32,
            ddspf_flags=DDPF.RGB.value | DDPF.ALPHAPIXELS.value if 0 < texture_format.value < 9 and not use_dx10 else \
                        DDPF.RGB.value if texture_format in (DDS_FORMAT.BGR8, DDS_FORMAT.R8) else \
                        DDPF.FOURCC.value,
            ddspf_fourCC=0x71 if texture_format == DDS_FORMAT.ARGB16 else \
                         0x74 if texture_format == DDS_FORMAT.ARGB32 else \
                         DDS_FORMAT.DX10.fourCC if use_dx10 and texture_format not in (DDS_FORMAT.BGR8, DDS_FORMAT.R8) else \
                         0 if 0 < texture_format.value < 14 and texture_format.value != 11 else \
                         texture_format.fourCC,
            ddspf_RGBBitCount=bpp if texture_format.value in (*range(1,9), 12, 13) else 0,
            ddspf_RBitMask=0x00FF0000 if texture_format.value in (*range(5,9), 12) else (1 << bpp) - 1 if texture_format == DDS_FORMAT.R8 else 0,
            ddspf_GBitMask=0x0000FF00 if texture_format.value in (*range(5,9), 12) else 0,
            ddspf_BBitMask=0x000000FF if texture_format.value in (*range(5,9), 12) else 0,
            ddspf_ABitMask=0xFF000000 if texture_format.value in range(5,9) else 0,
            caps=DDSCAPS.TEXTURE.value,
            caps2=0,
            caps3=0,
            caps4=0,
            reserved2=0
        )
        if bpp == 16:
            dds_header.ddspf_RBitMask = 0x00000F00
            dds_header.ddspf_GBitMask = 0x000000F0
            dds_header.ddspf_BBitMask = 0x0000000F
            dds_header.ddspf_ABitMask = 0x0000F000
        """ Not using Pixelformat RGBA?
        elif bpp == 64: # 9
            dds_header.ddspf_RBitMask = 0x0000FFFF
            dds_header.ddspf_GBitMask = 0xFFFF0000
            dds_header.ddspf_BBitMask = 0x0000FFFF
            dds_header.ddspf_ABitMask = 0xFFFF0000
        elif bpp == 128: # 10
            dds_header.ddspf_RBitMask = 0xFFFFFFFF
            dds_header.ddspf_GBitMask = 0xFFFFFFFF
            dds_header.ddspf_BBitMask = 0xFFFFFFFF
            dds_header.ddspf_ABitMask = 0xFFFFFFFF
        """

        if dds_header.mipMapCount:
            dds_header.flags |= DDS_HEADER_FLAGS.MIPMAP.value
            dds_header.caps |= DDSCAPS.MIPMAP.value # Note: Originally used MIPMAPCUBE
        if cubemap:
            dds_header.caps |= DDSCAPS.COMPLEX.value
            dds_header.caps2 |= DDSCAPS2.ALLFACES.value
        if flag_table[i] & G1T_FLAG.NORMAL_MAP.value and dds_header.ddspf_flags & DDPF.FOURCC.value:
            # Can't have DDS_NORMAL with RGBA textures https://github.com/VitaSmith/gust_tools/issues/84
            dds_header.ddspf_flags |= DDPF.NORMAL.value


        if use_dx10:
            dxt10_hdr = DDS_HEADER_DXT10(
                dxgiFormat=DXGI_FORMAT.BC1_UNORM.value if texture_format == DDS_FORMAT.DXT1 else \
                           DXGI_FORMAT.BC2_UNORM.value if texture_format == DDS_FORMAT.DXT3 else \
                           DXGI_FORMAT.BC3_UNORM.value if texture_format == DDS_FORMAT.DXT5 else \
                           DXGI_FORMAT.BC4_UNORM.value if texture_format == DDS_FORMAT.BC4 else \
                           DXGI_FORMAT.BC7_UNORM.value if texture_format in (DDS_FORMAT.BC7, DDS_FORMAT.DX10) else \
                           DXGI_FORMAT.BC6H_UF16.value if texture_format == DDS_FORMAT.BC6H else \
                           DXGI_FORMAT.B8G8R8A8_UNORM.value if texture_format in (DDS_FORMAT.RGBA8, DDS_FORMAT.ARGB8) else \
                           -2,
                resourceDimension=2, # TEXTURE2D
                miscFlag=D3D11_RESOURCE_MISC_FLAG.TEXTURECUBE.value if cubemap else 0,
                arraySize=max(((extra_flags >> 28) & 0x0F) + ((extra_flags >> 12) & 0xF0), 1), # NB_FRAMES
                miscFlags2=0
            )
            if texHeader.unk4 & G1T_FLAG4_SRGB:
                dxt10_hdr.dxgiFormat += 1
                if texture_format in (DDS_FORMAT.RGBA8, DDS_FORMAT.ARGB8):
                    dxt10_hdr.dxgiFormat = DXGI_FORMAT.B8G8R8A8_UNORM_SRGB.value

        # Write header and data:
        path = output_folder / f'{i:04d}.dds'
        with path.open('wb') as dds:
            dds.write(b'DDS ')
            dds.write(pack(f'< {DDS_HEADER_STRUCT}', *astuple(dds_header)))
            if use_dx10:
                dds.write(pack(f'< {DDS_HEADER_DXT10_STRUCT}', *astuple(dxt10_hdr)))
            # frames per mipmap to img with mipmaps per frame
            tex_per_mm = texture['nb_frames'] * (6 if cubemap else 1)
            sz = texture_size // tex_per_mm
            for f in range(tex_per_mm):
                offset = 0 if texture_data else hdr.tableOffset + pos + tex_hdr_sz
                for l in range(texHeader.mip_count):
                    msz = mipmap_size(texture_format, l, dds_header.width, dds_header.height)
                    offset += f * msz
                    if texture_data:
                        dds.write(texture_data[f * sz + offset:f * sz + offset + msz])
                    else:
                        dds.write(data[f * sz + offset:f * sz + offset + msz])
                    offset += (texture['nb_frames'] - f) * msz
    # if not list only:
    path = output_folder / 'g1t.json'
    with path.open('w') as j:
        json.dump(json_data, j, indent=4)

def dds_to_g1t(input_folder: Path, flip_image: bool):
    path = input_folder / 'g1t.json'
    if not path.is_file():
        raise ValueError(f"'{path}' does not exist")

    with path.open('r') as f:
        json_data = json.load(f)
    dds_to_g1t_json(input_folder, json_data, flip_image)

def dds_to_g1t_json(input_folder: Path, json_data: dict, flip_image: bool):
    # filename = json_data.get('name', None)
    version_string = json_data.get('version', 0)
    version = int(version_string.encode().hex(), 16)
    if not version or int(version_string, 16) > 0x2710:
        raise ValueError(f"Unexpected G1T version {version_string}.")

    json_textures_array = json_data['textures']
    nb_textures = len(json_textures_array)
    json_extra_data_array = json_data.get('extra_data', [])
    extr_sz = len(json_extra_data_array)
    if not flip_image: flip_image = json_data.get('flip', False)
    platform = next((p for p in KNOWN_PLATFORMS if p.display_name == json_data['platform']), UNKNOWN_PLATFORM(int(json_data['platform'])))
    global E
    E = '>' if platform.name in ('SONY_PS2', 'NINTENDO_WII', 'NINTENDO_WIIU') else '<'
    default_texture_format = get_default_texture_format(platform)

    # show_info_head()

    flag_table = []
    offset_table = []
    data_offset = nb_textures * 4 + extr_sz * 2
    g1t_tex_data = bytes()

    for i in range(nb_textures):
        tex_type = json_textures_array[i].get('Type', 0)
        if tex_type not in (0x00, 0x01, 0x02) and tex_type not in TEXTURE_TYPE_TO_DDS_FORMAT:
            raise ValueError(f'Unsupported texture type 0x{tex_type:02x}.')
        # Read the DDS file
        path: Path = input_folder / json_textures_array[i]['name']
        texture_size = path.stat().st_size
        if texture_size < 5:
            raise ValueError(f"Data of '{path}' is not sufficient.")
        if texture_size > 0xFFFFFFFF:
            raise ValueError(f"'{path}' surpasses the max. size of {0xFFFFFFFF}.")
        with path.open('rb') as f:
            magic = f.read(4)
            if magic != b'DDS ':
                raise ValueError(f"'{path}' is not a DDS file.")
            data = bytearray(f.read()) # must be mutable
        dds_header = DDS_HEADER(*unpack_from(f'> {DDS_HEADER_STRUCT}', data))
        # Are both width and height a power of two?
        # WIP: Also check if height/width are larger than what we can represent with dx/dy
        cubemap = dds_header.caps & DDSCAPS.COMPLEX.value and dds_header.caps2 & DDSCAPS2.ALLFACES.value
        if cubemap and dds_header.caps2 & DDSCAPS2.ALLFACES.value != DDSCAPS2.ALLFACES.value:
            raise ValueError(f"Cannot handle cube maps with missing faces.")
        ddspf_rgba4cc = DDPF.ALPHAPIXELS.value | DDPF.FOURCC.value | DDPF.RGB.value
        if dds_header.ddspf_flags & ddspf_rgba4cc == DDPF.ALPHAPIXELS.value | DDPF.RGB.value:
            if dds_header.ddspf_RGBBitCount not in (16, 32, 64, 128):
                raise ValueError(f"'{path}' is not a supported ARGB texture.")
        elif dds_header.ddspf_flags & ddspf_rgba4cc == DDPF.RGB.value:
            if (dds_header.ddspf_RGBBitCount != 24 or
                dds_header.ddspf_RBitMask != 0x00ff0000 or
                dds_header.ddspf_GBitMask != 0x0000ff00 or
                dds_header.ddspf_BBitMask != 0x000000ff or
                dds_header.ddspf_ABitMask != 0x00000000):
                raise ValueError(f"'{path}' is not a supported RGB texture.")
        elif dds_header.ddspf_flags & ddspf_rgba4cc != DDPF.FOURCC:
            raise ValueError(f"'{path}' is not a supported texture.")
        extended_data: bool = json_textures_array[i]['extended_data']
        po2_fail = dds_header.width.bit_count() != 1 or dds_header.height.bit_count() != 1
        if po2_fail and not extended_data:
            # WIP: Can we fix that in here? with flags[0] | G1T_FLAG.EXTENDED_DATA.value
            # Also WIP: extended_data could use a 
            raise ValueError(f"Extended data flag must be set for textures with dimensions that aren't a power of two.")
        dds_payload_offset = 4 + dds_header.size # should always be 124
        # We may have a DXT10 additional header
        if dds_header.ddspf_fourCC == DDS_FORMAT.DX10.fourCC:
             dds_payload_offset += DDS_HDXT10_SZ
        texture_size -= dds_payload_offset
        texture_format = TEXTURE_TYPE_TO_DDS_FORMAT[tex_type] if tex_type in TEXTURE_TYPE_TO_DDS_FORMAT else \
                         default_texture_format
        min_mipmap_size = texture_format.dds_bpb
        if platform.name == 'NINTENDO_SWITCH': min_mipmap_size *= 0x40
        expected_texture_size = sum(mipmap_size(texture_format, j, dds_header.width, dds_header.height) for j in range(dds_header.mipMapCount - md))
        nb_frames = json_textures_array[i].get('nb_frames', 0)
        expected_texture_size *= nb_frames
        if cubemap: expected_texture_size *= 6
        if expected_texture_size > texture_size:
            raise ValueError(f"Expected_texture_size {expected_texture_size} > {texture_size}.")
        if (texture_size * 8) % texture_format.dds_bpp != 0:
            raise ValueError(f"Texture size should be a multiple of {texture_format.dds_bpp} bits")
        md = dds_header.mipMapCount - json_textures_array[i].get('mipmaps', 0)
        if md < 0:
            print(f'WARNING: Imported texture has {dds_header.mipMapCount} mipmaps, instead of {dds_header.mipMapCount - md} (original).')
            md = 0
        elif md > 0 and md != dds_header.mipMapCount:
            print(f'NOTE: Truncating number of mipmaps from {dds_header.mipMapCount} to {dds_header.mipMapCount - md}.')
        if expected_texture_size < texture_size:
            if md > 0 and md != dds_header.mipMapCount:
                print('NOTE: Reducing texture size')
            texture_size = expected_texture_size
        flag = json_textures_array[i].get('flag', [0])
        unknown_flags = json_textures_array[i].get('unknown_flags', [0])
        extended_data_flag = json_textures_array[i].get('extended_data_flag', 0)
        flag_table.append(flag)
        offset_table.append(data_offset + len(g1t_tex_data))
        extended_data_flag |= ((nb_frames & 0x0F) << 28) | ((nb_frames & 0xF0) << 12)
        nb_frames = max(nb_frames, 1)
        # only when little endian, but we save it in unmodified endianness, so IDK
        # for j in range(4): 
        #     unknown_flags[j] = unknown_flags[j] >> 4 | unknown_flags[j] << 4
        dds_height = dds_header.height // (2 if unknown_flags[0] & G1T_FLAG1_DOUBLE_HEIGHT else 1)

        # Write data:
        tex = G1TTextureInfo(0, tex_type, 0, *unknown_flags, int(extended_data), bytes())
        tex.set_mipSys(
            mip_count=dds_header.mipMapCount - md,
            z_mipmaps=json_textures_array[i].get('z_mipmaps', 0)
        )
        tex.set_dxdx(dds_header.width, dds_header)
        if E == '<':
            tex.unk1 = (tex.unk1 & 0x0F) << 4 | tex.unk1 >> 4
            tex.unk2 = (tex.unk1 & 0x0F) << 4 | tex.unk2 >> 4
            tex.unk3 = (tex.unk1 & 0x0F) << 4 | tex.unk3 >> 4
            tex.unk4 = (tex.unk1 & 0x0F) << 4 | tex.unk4 >> 4
            tex.extraHeaderVersion = (tex.extraHeaderVersion & 0x0F) << 4 | tex.extraHeaderVersion >> 4
        struct = '8B'
        if extended_data:
            esz = 5 if po2_fail else 3
            tex.extraDataSize = esz * 4
            tex.depth = json_textures_array[i].get('depth', 0.0)
            tex.flags = extended_data_flag
            if po2_fail:
                tex.width = dds_header.width
                tex.height = dds_height
                tex.dxdy = 0
            struct += f'If{esz - 2}I'
            
        dds_payload = data[dds_payload_offset:]
        if flip_image or (platform.name == 'NINTENDO_3DS' and tex_type in (0x09, 0x45)):
            dds_payload = flip_vertically(texture_format.dds_bpp, dds_payload, texture_size, dds_header.width)

        if tex_type in SWIZZLED:
            morton_order = 3 if platform.name in ('SONY_PS4', 'NINTENDO_3DS') else \
                           1 if platform.name == 'NINTENDO_WIIU' else \
                           int(log2(min(dds_header.width // texture_format.dds_bwh,
                                        dds_header.height // texture_format.dds_bwh))) # WiiU: Same for all mipmaps
            assert morton_order != 0
            width_factor = 2 if platform.name in ('SONY_PS4', 'NINTENDO_3DS') else \
                           16 // texture_format.dds_bpb if platform.name == 'NINTENDO_WIIU' else \
                           1
            add_width_fa = 8 if platform.name == 'NINTENDO_WIIU' else \
                           1
            # WIP: Handle morton for texture arrays & cubemaps
            offset = 0
            for j in range(dds_header.mipMapCount - md):
                msz = mipmap_size(texture_format, j, dds_header.width, dds_header.height)
                mw = max(add_width_fa * texture_format.dds_bwh, dds_header.width / (1 << j))
                mh = max(add_width_fa * texture_format.dds_bwh, dds_header.height / (1 << j))
                if dds_header.width / (1 << j) < mw:
                    dds_payload[offset:offset + msz] = tiling(texture_format, dds_header.width / (1 << j), mw, dds_payload[offset:offset + msz], max(min_mipmap_size, msz), True)
                dds_payload[offset:offset + msz] = mortonize(texture_format, morton_order, mw, mh, dds_payload[offset:offset + msz], max(msz, min_mipmap_size), width_factor)
                offset += msz
                if platform.name != 'NINTENDO_WIIU': morton_order += -1 if morton_order > 0 else 1
                if morton_order == 0: break

        if texture_format.value in range(1, 9) and texture_format.name[:4] != 'ARGB':
            dds_payload = rgba_convert(dds_payload, texture_format, 'ARGB')

        # Write header and data:
        g1t_tex_data += pack(E+struct, *tex.__dict__.values())
        # img with mipmaps per frame to frames per mipmap
        tex_per_mm = nb_frames * (6 if cubemap else 1)
        sz = texture_size // tex_per_mm
        offset = 0
        for l in range(dds_header.mipMapCount - md):
            msz = mipmap_size(texture_format, l, dds_header.width, dds_header.height)
            for f in range(tex_per_mm):
                g1t_tex_data += dds_payload[f * sz + offset:f * sz + offset + msz]
                if msz < min_mipmap_size:
                    g1t_tex_data += bytes(min_mipmap_size - msz)
            offset += msz

        # print(f'0x{tex_type:02x} 0x{G1T_HEADER_SZ + nb_textures * 4 + offset_table[i]:08x} 0x{data_offset + len(g1t_tex_data) - offset_table[i]:08x} {f'{dds_header.width}x{dds_header.height}':<10} {dds_header.mipMapCount - md:<7} {'A' if nb_frames > 1 else '-'}{'B' if E == '>' else '-'}{'C' if cubemap else '-'}{'D' if tex.depth != 0.0 else '-'}  {path.name}')

    hdr = G1THeader(
        magic=b'G1TG' if E == '>' else b'GT1G',
        chunkVersion=version,
        chunkSize=G1T_HEADER_SZ + nb_textures * 4 + data_offset + len(g1t_tex_data),
        tableOffset=G1T_HEADER_SZ + nb_textures * 4, # calcsize('I')
        textureCount=nb_textures,
        platform=platform.value,
        ASTCExtraInfoSize=extr_sz * 2 # calcsize('H')
    )
    # WIP: Might need a variant with data return values in the future
    with input_folder.with_suffix('.g1t').open('wb') as f:
        f.write(pack(E+G1T_HEADER_STRUCT, *astuple(hdr)))
        f.write(pack(f'{E} {2 * nb_textures}I', *flag_table, *offset_table))
        f.write(pack(f'{E} {extr_sz}H', *json_extra_data_array))
        f.write(g1t_tex_data)


# =================================================================
# Helper Functions
# =================================================================

def get_default_texture_format(platform: KNOWN_PLATFORMS|UNKNOWN_PLATFORM):
    """Get the default ARGB format for the platform"""
    return DDS_FORMAT.GRAB8 if platform.name in ['NINTENDO_DS', 'NINTENDO_3DS', 'SONY_PS4'] else \
           DDS_FORMAT.ARGB8 if platform.name in ['SONY_PSV', 'NINTENDO_SWITCH'] else \
           DDS_FORMAT.RGBA8 # PC and other platforms

def rgba_convert(buf: bytearray, f: DDS_FORMAT, out_order: str) -> bytearray:
    """
    Convert an image buffer's RGBA channels in the specified in format (f) to the specified out_order (channels only).
    Note: This is based on assumptions. It wasn't tested or verified.
    """
    in_order = f.name[:4]
    if in_order == out_order:
        return buf

    bpp = f.dds_bpp
    assert bpp % 8 == 0
    A = in_order.index(out_order[0])
    B = in_order.index(out_order[1])
    C = in_order.index(out_order[2])
    D = in_order.index(out_order[3])
    for p in range(0, len(buf), bpp // 8):
        if bpp == 32:
            buf[p:p + 4] = buf[p + A], buf[p + B], buf[p + C], buf[p + D]
        elif bpp == 16:
            pixel = (buf[p] >> 4, buf[p] & 0x0F, buf[p + 1] >> 4, buf[p + 1] & 0x0F)
            buf[p:p + 2] = pixel[A] << 4 | pixel[B], pixel[C] << 4 | pixel[D]
        elif bpp == 24:
            buf[p:p + 3] = buf[p + A], buf[p + B], buf[p + C] # WIP: No support for BGR?
    return buf

# Is this the simplest math possible?
def inflate_bits(x: int) -> int:
    """"Inflate" a 32 bit value by interleaving 0 bits at odd positions."""
    x &= 0x0000FFFF
    x = (x | (x << 8)) & 0x00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F
    x = (x | (x << 2)) & 0x33333333
    x = (x | (x << 1)) & 0x55555555
    return x

def deflate_bits(x: int) -> int:
    """"Deflate" a 32-bit value by deinterleaving all odd bits."""
    x &= 0x55555555
    x = (x | (x >> 1)) & 0x33333333
    x = (x | (x >> 2)) & 0x0F0F0F0F
    x = (x | (x >> 4)) & 0x00FF00FF
    x = (x | (x >> 8)) & 0x0000FFFF
    return x

def mortonize(f: DDS_FORMAT, morton_order: int, width: int, height: int, buf: bytearray, size: int, wf: int) -> bytearray:
    """
    Apply or reverse a Morton transformation, a.k.a. a Z-order curve, to a texture.
    If morton_order is negative, a reverse Morton transformation is applied.
    WIP: This is complicated math and I don't know how to improve it or how to insert the correct bytearray. I might use a module in the future
    """
    bits_per_element = f.dds_bpp * f.dds_bwh ** 2 * wf
    bytes_per_element = bits_per_element // 8
    width //= f.dds_bwh * wf
    height //= f.dds_bwh
    num_elements = size // bytes_per_element
    k = abs(morton_order)
    reverse = morton_order != k

    assert bits_per_element % 8 == 0
    assert bytes_per_element * width * height == size
    assert width < 0x10000 and height < 0x10000
    assert width % (1 << k) == 0
    assert height % (1 << k) == 0
    assert k <= max(width, height).bit_length()

    tile_width = 1 << k
    tile_size = tile_width * tile_width
    mask = tile_size - 1
    tmp_buf = bytearray(size)

    for i in range(num_elements):
        if reverse:
            z = i & mask
            x = deflate_bits(z >> 1)
            y = deflate_bits(z >> 0)
            x += ((i // tile_size) % (width // tile_width)) * tile_width
            y += ((i // tile_size) // (width // tile_width)) * tile_width
            j = y * width + x
        else:
            x, y = i % width, i // width
            j = ((inflate_bits(x) << 1) | (inflate_bits(y) << 0)) & mask
            j += ((y // tile_width) * (width // tile_width) + (x // tile_width)) * tile_size

        assert j < num_elements
        tmp_buf[j * bytes_per_element:(j + 1) * bytes_per_element] = buf[i * bytes_per_element:(i + 1) * bytes_per_element]

    return tmp_buf

def tiling(f: DDS_FORMAT, tile_size: int, width: int, buf: bytearray, size: int, untile: bool) -> bytearray:
    # WIP: This could be improved or use a module (like mortonize)
    bytes_per_element = f.dds_bpb
    tile_size //= f.dds_bwh
    width //= f.dds_bwh

    assert tile_size % f.dds_bwh == 0
    assert width % f.dds_bwh == 0
    assert bytes_per_element != 0
    assert size % bytes_per_element == 0
    assert size % (tile_size * tile_size) == 0
    assert width % tile_size == 0

    tmp_buf = bytearray(size)

    for i in range(size // bytes_per_element // tile_size // tile_size):
        tile_row = i // (width // tile_size)
        tile_column = i % (width // tile_size)
        tile_start = tile_row * width * tile_size + tile_column * tile_size
        for j in range(tile_size):
            tiled = slice(bytes_per_element * (i * tile_size * tile_size + j * tile_size), bytes_per_element * ((i + 1) * tile_size * tile_size + (j + 1) * tile_size))
            untiled = slice(bytes_per_element * (tile_start + j * width), bytes_per_element * (tile_start + (j + 1) * width))
            tmp_buf[untiled if untile else tiled] = buf[tiled if untile else untiled]

    return tmp_buf

def mipmap_size(f: DDS_FORMAT, l: int, w: int, h: int) -> int:
    bwh = f.dds_bwh
    return max(max(1, ((w // (1 << l) + bwh - 1) // bwh)) *
               max(1, ((h // (1 << l) + bwh - 1) // bwh)) *
               f.dds_bpb, 1)

def flip_vertically(bytes_per_pixel: int, buf: bytearray, size: int, width: int) -> bytearray:
    # works with bytes or bytearray
    line_size = width * bytes_per_pixel
    assert size % line_size == 0

    tmp_buf = bytearray()

    for i in range(size, 0, -line_size):
        tmp_buf.append(buf[i - line_size:i]) # bytes: tmp_buf += buf[i - line_size:i]

    return tmp_buf

""" backup ProjectG1M version:
def flip_vertically(pixels: bytes, width: int, height: int, bytes_per_pixel: int) -> bytes:
    line_size = width * bytes_per_pixel
    low = 0
    high = (height - 1) * line_size

    while low < high:
        row = pixels[low:low + line_size]
        pixels[low:low + line_size] = pixels[high:high + line_size]
        pixels[high:high + line_size] = row
        low += line_size
        high -= line_size

    return pixels

WIP: Non-DDS formats. There might be no way to do this without Noesis.

Decompress PVRTC
if not rawFormat.find('PVRTC') == 0:
    untiledTexData = rapi.Image_DecodePVRTC(data[pos:], dataSize, texHeader.width, texHeader.height, pvrtcBpp)
    rawFormat = 'r8g8b8a8'
    dataSize *= 16

Decompress ASTC
if not rawFormat.find('ASTC') == 0:
    rawFormat = EG1TASTCFormat[formatList[i]]
    blockSizes = rawFormat.split('_')
    pBlockDims = [blockSizes[1], blockSizes[2], 1]
    pImageSize = [texHeader.width, texHeader.height, 1]
    untiledTexData = rapi.Image_DecodeASTC(rapi.Noesis_UnpooledAlloc(dataSize * 16), data[pos:], dataSize, pBlockDims, pImageSize)
    rawFormat = 'r8g8b8a8'
    dataSize *= 16

Decompress ETC
if not rawFormat.find('ETC') == 0:
    untiledTexData = rapi.Image_DecodeETC(rapi.Noesis_UnpooledAlloc(dataSize * 8), data[pos:], dataSize, texHeader.width, texHeader.height, rawFormat.split('_')[-1].upper())
    dataSize *= 8
    if bSpecialCaseETC:
        texHeader.height //= 2
        alphaOffset = texHeader.width * texHeader.height * 4
        for j in range(texHeader.width * texHeader.height):
            untiledTexData[4 * j + 3] = untiledTexData[alphaOffset + 4 * j]
        untiledTexData = rapi.Image_DecodeETC(untiledTexData, data[pos:], dataSize, texHeader.width, texHeader.height, 'RGBA')
        dataSize *= 8
    rawFormat = 'r8g8b8a8'

Decompress 3DS
if not rawFormat.find('3DS') == 0:
    untiledTexData = rapi.Image_DecodePICA200ETC(rapi.Noesis_UnpooledAlloc(texHeader.width * texHeader.height * 16), data[pos:], texHeader.width, texHeader.height, b3DSAlpha, 0, 0)
    untiledTexData = flip_vertically(untiledTexData, width, height, 4)
    rawFormat = 'r8g8b8a8'
if untiledTexData:
    bShouldFreeUntiled = True
if bRaw:
    texData = rapi.Noesis_ImageDecodeRaw(untiledTexData, dataSize, texHeader.width, texHeader.height, rawFormat[0])
elif bNormalized:
    texData = rapi.Noesis_ConvertDXT(texHeader.width, texHeader.height, untiledTexData, fourccFormat)
else:
    params = convertDxtExParams_t()
    params.ati2ZScale = 0.0
    params.ati2NoNormalize = True
    params.decodeAsSigned = params.resvBB = params.resvBC = False
    texData = rapi.Noesis_ConvertDXTEx(texHeader.width, texHeader.height, untiledTexData, dataSize, params, 0)

class KHM:
    name: str

    def __init__(self, data: str, prevIndex: int):
        hs = calcsize(KHM_HEADER_STRUCT)
        header = KHMHeader(*unpack_from(E+KHM_HEADER_STRUCT, data))
        rawFormat = 'r8g8b8'
        header.width += 1
        header.height += 1
        rawSize = header.width * header.height
        dataSize = rawSize * 3
        texture = tuple(255 * x[0] // 0xFFFFFFFF for x in iter_unpack(E+'I', data[hs:hs + 4 * rawSize]))
        # or better: texture = ((i for i in data[x:x + 4]) for x in range(hs, hs + 4 * rawSize, 4)) ?
        # WIP: Now, we need to decode this data without Noesis
        self.name = f'{prevIndex + 1}.dds'

    # WIP:
    def from_dict(self, d: dict):
        t = KHM(**d)
        return t
        # https://stackoverflow.com/questions/59250557/how-to-convert-a-python-dict-to-a-class-object
        # t.content = [KHMHeader(**c) for c in t.content]
"""
