# Koei Tecmo's Gust files extractor and combiner for MUA3
# by eArmada8, Joschuka and three-houses-research-team, yretenai (creator of Cethleann), ..., ak2yny
# WIP: using byte stream instead of bytes could speed up the process: io.BytesIO(data) as f (f.read(4)), but bytearray should be the fastest


import json, glob, subprocess
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, unpack, calcsize, unpack_from

from pyquaternion import Quaternion

from MUA3_Formats import GUST_MAGICS, getFileExtension
from MUA3_BIN import combine, get_offsets
from MUA3_ZL import backup, un_pack, _re_pack, _un_pack

# from Blender.g1m_export_meshes import parseG1M
from lib.lib_gust import *
from lib.lib_g1m import calc_abs_rotation_position, EG1MGVADatatype, G1MGVASemantic, G1MHeader, G1MG, G1MM, G1MS, IS_G1MS_UNORDERED # *
from lib.lib_g1t import G1T
# from lib.lib_g2a import G1A, G2A
from lib.lib_nun import NUNO, NUNV, NUNS
from lib.lib_oid import GLOBAL2OID, OID


# Import settings
TRANSFORM_CLOTH_MESH = True
MAX_CTRL_PTS = 512 # Max number of control points, maximum value before being broken in subsets, as seen in both the NUNO sections and the vshader

# WIP: Are these for Noesis only?
# https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/Options.h
bMERGE = bMERGEG1MONLY = bG1TMERGEG1MONLY = bADDITIVE = bCOLOR = bDISPLAYDRIVER = bDISABLENUNNODES = bNOTEXTURERENAME = bLOADALLLODS = False
bENABLENUNAUTORIG = True
# overwrite = False, write_buffers = True, cull_vertices = True, write_empty_buffers = False, preserve_trianglestrip = False
# g1tConsolePath[MAX_NOESIS_PATH]  ?

ZERO_INT = bytes(4)
SKELETON_INTERNAL_INDEXP1 = 0
SKELETON_LAYER = 1 # Custom layering system from Noesis plugin
G1MGs = G1MMs = G1MSs = NUNOs = NUNVs = NUNSs = SOFTs = [] # WIP: Might need a common dict with ID, so to preserve the order
# G1MSs = { True: [], False: [] }
g1t_extract = './g1t_extract.exe'

# WIP: Currently unused, but keep, in case find use for it
offsets = {
    'G1MM': [],
    'G1MS': [],
    'G1MG': [],
    'NUNO': [],
    'NUNV': [],
    'NUNS': [],
    'SOFT': []
}

#def has_suffix

""" WIP:
Noesis plugin uses first byte check for file types, it seems like we do that manually or not at all. Might be better to just work with the magic here.

def transformPosF(data: str, vertexCount: int, stride: int, mat: matrix):
    for src in iter_unpack(f'{E} 3f{stride - 12}x', data[:stride * vertexCount]):
        tmp = g_mfn.Math_TransformPointByMatrix(mat, src, ?)
        src = g_mfn.Math_VecCopy(tmp, src)
        # swap endian?
    return?

is dst an empty buffer and we can just append, instead of inserting (which wouldn't work in Pyhon on an empty list, etc, only on an empty byte string or byte array).

def transformPosHF(data2: str, data:str, vertexCount: int, stride: int, mat: ? = None):
    dst = list(iter_unpack(E+'f', data2))
    for i, src in enumerate(iter_unpack(f'{E} 3H{stride - 6}x', data[:stride * vertexCount])):
        tmp1 = [g_mfn.Math_GetFloat16(s) in s for src]
        tmp2 = [0.0, 0.0, 0.0]
        if mat:
            tmp2 = g_mfn.Math_TransformPointByMatrix(mat, tmp1, tmp2)
            dst[3 * i: 3 * i + 3] = g_mfn.Math_VecCopy(tmp2, dst[3 * i: 3 * i + 3])
        else:
            dst[3 * i: 3 * i + 3] = g_mfn.Math_VecCopy(tmp1, dst[3 * i: 3 * i + 3])
        # dst swap endian?
    return dst

If needed: https://github.com/Joschuka/Project-G1M/blob/main/Source/Public/Utils.h#L188
def skinSMeshW(jointWB: str, jointWBType: EG1MGVADatatype, jointWB2: str, jointWB2Type: EG1MGVADatatype, vertexCount: int, stride: int, bHas8Weights: bool):
    return jointWBFinal

def genColor3F(data: str, data2:str, vertexCount: int, stride: int):
    dst = list(iter_unpack(E+'f', data2)) # or dst = ()
    for src in iter_unpack(f'{E} 3f{stride - 12}x', data[:stride * vertexCount]):
        dst[4 * i:4 * i + 3] = list(src)
        dst[4 * i + 3] = 1
        # or dst += src + (1,)
        # swap back endian, but this would mean that we insert it back to a buffer (pack) or even write a file again
"""

def extractTexture(data: str, noeTex: list):
    G1T(data, noeTex) # WIP: not implemented
    # WIP: rename texture

""" WIP: Do we need this or is OBJD below enough?
def extractMap(data: str, numMdl: int):
    objd = OBJD(data)
    # WIP: We could process it directly from each data section in the loop from UnpackBundles. Should make the ProcessModel code cleaner too.
    # WIP: Need to load a paired datatable (*.datatable) file, possibly needs user input or something.
    if not UnpackBundles(datatable.read_bytes(), bundleIDtoG1MOffsets, bundleIDtoG1MSizes):
        return None
    ProcessModel(data, numMdl, True, bundleIDtoG1MOffsets, bundleIDtoG1MSizes, , objd.section1IDToBundleG1MID, objd.entityMatrices)


def OBJD(input_file: Path, datatable: Path):
    "Map objects
    WIP: detect datatable? input_file.parent.iterdir()
    It seems like MUA3 doesn't use this, so it stays in an unfinished state. Ideally, would process each section that was extracted.
    "
    bundleIDtoG1MOffsets = {}
    bundleIDtoG1MSizes = {}
    data_dt = datatable.read_bytes()
    if not OBJD_UnpackBundles(data_dt, bundleIDtoG1MOffsets, bundleIDtoG1MSizes):
        return None
    data = input_file.read_bytes()
    mapMatrices = [] # can they be processed directly?
    ohs = calcsize(OBJD_HEADER_STRUCT)
    header = OBJDHeader(*unpack(E+OBJD_HEADER_STRUCT, data[:ohs]))
    # Section 0: skip Section header and content
    pos = ohs + 0x10 + header.section0EntryCount * 0x40
    # Section 1: always little endian?
    pos += 0x10 # skip Section header
    end1 = pos + 1024 * header.section1EntryCount
    section1IDToBundleG1MID = tuple(iter_unpack('< 464xH53xB504x', data[pos:end1])) # skip huge amounts of data
    # Section 2: always little endian?, section2EntryCount should correspond with database
    pos = end1 + 0x10 # skip Section header
    end2 = pos + 64 * header.section2EntryCount
    for x in iter_unpack('< 3f4x7f8xI8x', data[pos:end2]): # skip some data
        scale = x[:3]
        rotation = x[3:7]
        position = x[7:10]
        section1ID = x[10]
        bundleID, g1mID = section1IDToBundleG1MID[section1ID]
        pos = bundleIDtoG1MOffsets[bundleID][g1mID]
        ParseG1M(data_dt[pos:pos + bundleIDtoG1MSizes[bundleID][g1mID]], paths) # WIP paths: need related files or merge earlier
            # WIP: Need working math here
            # mat = (Quaternion(*rotation).ToMat43().GetTranspose() * RichMat43(scale[0], 0, 0, 0, scale[1], 0, 0, 0, scale[2], 0, 0, 0)).m
            # mat = g_mfn.Math_VecCopy(*position, mat.o)
            # entityMatrices.append((section1ID, mat))
        mapMatrices.append((scale, rotation, position)) # WIP: or process directly
    # Section 3: we don't have useful info to get from this section

def OBJD_UnpackBundles(data: str, bundleIDtoG1MOffsets: dict, bundleIDtoG1mSizes: dict) -> bool:
    entryCount, firstOffset, firstSize = unpack('< 3I', data[:12]) # always little endian?
    bundleCount, = unpack('< I', data[firstOffset:firstOffset + 4]) # always little endian?
    end = firstOffset + 4 * (1 + bundleCount)
    #bundleSizes = unpack(f'< {bundleCount}I', data[firstOffset + 4:end]) # always little endian?
    pos = dirtyAlign(data, end, 4)
    # Parsing bundles, for each of them, read only first mdlk
    for i, s in enumerate(unpack(f'< {bundleCount}I', data[firstOffset + 4:end])): # always little endian?
        mdlkCount, = unpack('< I', data[pos:pos + 4]) # always little endian?
        p = dirtyAlign(data, 4 + mdlkCount * 4, 4)
        g1mCount, = unpack('< 8xI4x', data[p:p + 16]) # always little endian?, skip rest of header
        p += 16
        bundleIDtoG1MOffsets[i] = []
        bundleIDtoG1mSizes[i] = []
        for _ in range(g1mCount):
            chunkSize = GResourceHeader(*unpack(E+III_STRUCT, data[p:p + 12])).chunkSize
            bundleIDtoG1MOffsets[i].append(p)
            bundleIDtoG1mSizes[i].append(chunkSize)
            p += chunkSize
            # bad check?
            bSuccess = not ((E == '>') ^ (data[p] == b'\x47'))
            if not bSuccess: break
        pos += s
    return bSuccess

WIP: Working on a solution in OBJD directly
if bIsMap:
    for matInfo in entityMatrices:
        pass
if bIsMap: pass # rapi.rpgSetTransform(mapMatrices[i])
"""

def ProcessModel(input_file: Path, data: str, numMdl: int, bundleIDtoG1MOffsets: dict = {}, bundleIDtoG1MSizes: list = {}, section1IDToBundleG1MID: list = [], entityMatrices: list = []):
    print(f'Processing {input_file.name}...')
    """WIP: Need this data?:
    bool bMergeSeveralInternals
    framerate = 0
    //g1m
    std::vector<std::string> g1mPaths;
    std::vector<int> fileLengths;
    std::vector<BYTE*> fileBuffers;
    //g1t
    std::vector<std::string> g1tPaths;
    std::vector<int> g1tFileLengths;
    std::vector<BYTE*> g1tFileBuffers;
    std::vector<uint32_t> g1tTextureOffsets;
    //oid
    bool bAlreadyHasOid = false;
    std::vector<std::string> oidPaths;
    std::vector<int> oidFileLengths;
    std::vector<BYTE*> oidFileBuffers;
    //g1a
    std::vector<std::string> g1aPaths;
    std::vector<int> g1aFileLengths;
    std::vector<BYTE*> g1aFileBuffers;
    std::vector<std::string> g1aFileNames;
    //g2a
    std::vector<std::string> g2aPaths;
    std::vector<int> g2aFileLengths;
    std::vector<BYTE*> g2aFileBuffers;
    std::vector<std::string> g2aFileNames;

    //unpooled Buffers
    std::vector<void*> unpooledBufs;

    //Offsets to the relevant G1M subSections
    std::vector<uint32_t>G1MSOffsets;
    std::vector<uint32_t>G1MMOffsets;
    std::vector<uint32_t>G1MGOffsets;
    std::vector<uint32_t>NUNOOffsets;
    std::vector<uint32_t>NUNVOffsets;
    std::vector<uint32_t>NUNSOffsets;
    std::vector<uint32_t>SOFTOffsets;

    //Subsections data containers
    std::vector<G1MS<bBigEndian>>internalSkeletons;
    std::vector<G1MS<bBigEndian>>externalSkeletons;
    std::vector<G1MS<bBigEndian>*>G1MSPointers;
    std::vector<int> NUNOFileIDs;
    std::vector<int> NUNVFileIDs;
    std::vector<int> NUNSFileIDs;
    std::vector<int> SOFTFileIDs;

    //NUN maps
    std::map<uint32_t, std::vector<uint32_t>> fileIndexToNUNO1Map;
    std::map<uint32_t, std::vector<std::pair<uint32_t, int>>> fileIndexToNUNO3Map; //The second value is the subset index in the nunoSubsets array
    std::map<uint32_t, std::vector<uint32_t>> fileIndexToNUNV1Map;
    std::vector<std::array<uint32_t,512>> nunoSubsets; //MAX_CTRL_PTS is the max number of CPs in the shader for now, it may change eventually

    //Maps containers
    std::vector<RichVec3> mapPositions;
    std::vector<RichQuat> mapRotations;
    std::vector<modelMatrix_t> mapMatrices;

    //Meshes
    std::vector<mesh_t> driverMeshes;

    //Fixes and hacks
    bool bIsSkeletonOrigin = true;
    RichMat43 rootCoords;

    -----------
    BLENDER WIP
    -----------
    # WIP: Should only pick each set of files separately. OID first, if exist (maybe unless no skeleton is involved, but that makes things complicated). Then skeleton, etc. as below.
    if bMERGE:
        e_f = ['.g1m'] if bMERGEG1MONLY else ['.g1m', '.g1t', '.g1a', '.g2a']
        fileID = 0
        paths = [p for p in input_file.parent.iterdir() if p.suffix.casefold() in e_f] if bMERGE else [input_file]
        for p in input_file.parent.iterdir():
            e = p.suffix.casefold()
            if e in e_f and p.stat().st_size > 0:
                fb = p.read_bytes()
                # WIP: g1mCount is this important?
                if e == '.g1m':
                    pass # WIP: Neet to read content and get lists of joints (for consistent numbering), and...?
                elif e == '.g1t':
                    pass # .g1t and oid seem to be the only files that can be read in advance
                elif e == '.g1a':
                    pass # need skel data first
                elif e == '.g2a':
                    pass # need skel data first
                fileID += 1
            elif e == '.oid' or p.name[-7:].casefold() == 'oid.bin':
                OID(p.read_bytes())
    else:
        # data...
        _ = (T(p.read_bytes()) for p in paths if p.suffix.casefold() == '.g1m') #WIP: or input_file.parent.glob(*.g1m)

    # WIP: Need a better code for merging and multi file processing (comand line would do with external iteration (not include other geometries), Blender I have to learn first.
    e_f = ['.g1m'] if bMERGEG1MONLY else ['.g1m', '.g1t', '.g1a', '.g2a']
    paths = [p for p in input_file.parent.iterdir() if p.suffix.casefold() in e_f] if bMERGE else [input_file]
    fileID = 0

    # WIP: or input_file.parent.glob(*.g1t) and bMERGE...
    # WIP: Might need external app to convert and import png/tga/dds into Blender, at least temporarily.
    textures = [G1T(p.read_bytes(), i) for i, p in enumerate(paths) if p.suffix.casefold() == '.g1t']
        # animList = []
        for p in (p for p in paths if p.suffix.casefold() in ['.g1a', '.g2a']):
            with p.open('rb') as f: magic = f.read(4)
            if getFileExtension(magic, E == '>') not in ['.g1a', '.g2a']: continue
            ga = G1A(p.read_bytes(), globalToFinal) if e == '.g1a' else G2A(p.read_bytes(), globalToFinal)
            # WIP: Change to not use Noesis, so instead:
            # animation-name = p.stem
            # animation-bone-link = ga.animData.keys()[i] for i in range(len(ga.animData))
            # animation-bone-data = ga.animData[animation-bone-link] -> in g2a it's a dictionary of times/frames (keys) and matrix datas
            # animation-framerate = ga.framerate
            # if bADDITIVE, each bone should be multiplied by bind matrix (which is?)
    """

    if joints and bMERGE: # WIP: Noesis joints, need equivalent that supports globalToFinal) and has a name property
        """
        # it seems to be useless to check whether there are OIDs already
        for o in (p for p in input_file.parent.iterdir() if p.suffix.casefold() == '.oid' or p.name[-7:].casefold() == 'oid.bin'):
            OID(o.read_bytes(), joints, globalToFinal) # Updates joints...
            # WIP: Could possibly remove this and just import OID files as lists/dictionaries and get the name on joint construction
        """
    for i, data in enumerate(G1MGs): # WIP: Need a solution if multiple files, as to get the relevant information. It seems like i is for multiple files only, as g1m files don't seem to contain multiple of them
        # WIP: Relevant options? (duplicates): cull_vertices = True, write_empty_buffers = False, preserve_trianglestrip = False
        # WIP: The form of data that was read in advance is important. Will probably be the byte string.
        # WIP: Whatever's possible should be added to this loop (if not required to be read, counted, etc. in advance, this includes NUN and skeletons)
        # WIP: It might make more sense to read the G1MG in advance, instead of giving the data section (depending on what's required to read it)
        # WIP: Skeleton for each geometry? not sure how the counting checks out
        # if skeleton external, use first internal skeleton and external skeleton ?? I am completely lost as to how this is supposed to happen < seems to be important that they match (although I don't know how to figure this out)
        # WIP - Update philosophy: Parse one set of mdl at a time, only regard extracted g1m, etc. if 0001 - ... in the same folder. | s = G1MSs[i] if len(G1MSs) > i else None # IMPORTANT, G1MSs must be for the same file!
        # IMPORTANT: NUN sections must have been parsed beforehand
        g1mg = G1MG(data,
            s if s and s.bIsInternal or not s else (s for s in G1MSs if s.bIsInternal)[0] if SKELETON_INTERNAL_INDEXP1 else None,
            None if s and s.bIsInternal else s,
            globalToFinal)
        g1mm = G1MMs[i]
        driverMesh_fmt = DriverMesh()
        # Retrieve LOD and physics type from section 9 (MeshGroups)
        for group in g1mg.meshGroups[:len(g1mg.meshGroups) if bLOADALLLODS else 1]:
            if not bLOADALLLODS or not group.Group: # submeshes, or use "if group.meshes", WIP: What to do if there are groups (and no meshes)
                for mesh in group.meshes:
                    previousVBIndex = -1
                    for index in mesh.indices:
                        # mesh = submesh_lod
                        # submesh and group.meshes[].indices seem to match (?)
                        submesh = g1mg.submeshes[index]
                        # subindex is enumeration of g1mg.submeshes
                        # generate_submesh(subindex, data, g1mg, s, cull_vertices (bool), preserve_trianglestrip = (bool))
                        mesh_name = f'model_{i}_submesh_{index}' + (f'_LOD{group.LOD}' if bLOADALLLODS else '')
                        mat_name = f'model_{i}_mat_{index}'
                        # WIP: Need a code to add textures without Noesis, and find a solution for multiple texture input files
                        for textureInfo in g1mg.materials[submesh.materialIndex].g1mgTextures:
                            if textureInfo.textureType == 1: # and not bHasDiffuse
                                # bHasDiffuse = True
                                if textureInfo.layer == 1: pass # UV1?
                            if textureInfo.textureType == 3: # and not bHasNormal
                                pass

                        if joints: # WIP: from before the start of the enumerate(G1MGs) loop!! (But I could probably make a better check)
                            # WIP: What is jointPalette and what do I do with it?
                            jointPalette = g1mg.jointPalettes[submesh.bonePaletteIndex]
                            # for j, b in enumerate(jointPalette.jointMapBuilder): jointMap[3 * j] = b
                            # Alternative way without jointMapBuilder:
                            jointMap = lib_g1m.generate_vgmap(submesh.bonePaletteIndex, g1mg, s)
                        if previousVBIndex == submesh.vertexBufferIndex:
                            # WIP: Use same buffer or just work on the same section doesn't make much difference in Python, probably
                            # 
                            pass

                        previousVBIndex = submesh.vertexBufferIndex
                        # WIP: How to process VB without Noesis?
                        ibuf = g1mg.indexBuffers[submesh.indexBufferIndex]

                        # for cloth type1
                        cPIdx1Type = EG1MGVADatatype.Dummy # etc

                        # for cloth type2
                        jointIdBType = EG1MGVADatatype.Dummy # etc

                        # WIP: Big amount of assignments to see if there are any (1 or more?), maybe there's a better way
                        for attribute in g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes:
                            vbuf = g1mg.vertexBuffers[attribute.bufferID]
                            match attribute.semantic:
                                case 'POSITION':
                                    if attribute.dataType == EG1MGVADatatype.Float_x3 or attribute.dataType == EG1MGVADatatype.Float_x4:
                                        if mesh.meshType == 1:
                                            controlPointsWeightsSet1 = vbuf.bufferAdress + attribute.offset
                                            phys1Stride = vbuf.stride # WIP: There might be a better way to filter out the correct vbuf for later use of stride and count
                                            phys1Count = vbuf.count
                                        elif mesh.meshType == 2:
                                            # WIP: Address and buffer are re-written for each matching attribute? Seems wrong. Need more info.
                                            posB = data[vbuf.bufferAdress + attribute.offset:]
                                        elif bIsSkeletonOrigin: # WIP: See above
                                            # WIP: Insert with root 0 0 0
                                            # rapi.rpgBindPositionBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                        else:
                                            # WIP: insert at custom origin, transform by matrix
                                            # transformPosF(data[vbuf.bufferAdress + attribute.offset:], vbuf.count, vbuf.stride, rootCoords.m)
                                            # rapi.rpgBindPositionBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.HalfFloat_x4:
                                        if bIsSkeletonOrigin: # WIP: See above
                                            # WIP: Insert with root 0 0 0
                                            # rapi.rpgBindPositionBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            pass
                                        else:
                                            # WIP: insert at custom origin, transform by matrix
                                            # posB = transformPosHF(data[vbuf.bufferAdress + attribute.offset:], vbuf.count, vbuf.stride, rootCoords.m)
                                            # rapi.rpgBindPositionBuffer(posB, RPGEODATA_FLOAT?, 12)
                                            pass
                                case 'NORMAL':
                                    if attribute.dataType == EG1MGVADatatype.Float_x3 or attribute.dataType == EG1MGVADatatype.Float_x4:
                                        if mesh.meshType == 1:
                                            depthFromDriver = data[vbuf.bufferAdress + attribute.offset:]
                                        else:
                                            # rapi.rpgBindPositionBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.HalfFloat_x4:
                                        # rapi.rpgBindPositionBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                        pass
                                case 'TEXCOORD':
                                    if attribute.dataType == EG1MGVADatatype.Float_x2:
                                        if attribute.layer == 0:
                                            # rapi.rpgBindUV1Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                        elif attribute.layer == 1:
                                            # rapi.rpgBindUV2Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.Float_x4:
                                        if attribute.layer == 0 or attribute.layer == 1:
                                            # rapi.rpgBindUV1Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            # rapi.rpgBindUV2Buffer(data[vbuf.bufferAdress + attribute.offset + 8:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.HalfFloat_x2:
                                        if attribute.layer == 0:
                                            # rapi.rpgBindUV1Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            pass
                                        elif attribute.layer == 1:
                                            # rapi.rpgBindUV2Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.HalfFloat_x4:
                                        if attribute.layer == 0 or attribute.layer == 1:
                                            # rapi.rpgBindUV1Buffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            # rapi.rpgBindUV2Buffer(data[vbuf.bufferAdress + attribute.offset + 4:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.UByte_x4:
                                        controlPointRelativeIndices4 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx4Type = EG1MGVADatatype.UByte_x4
                                    elif attribute.dataType == EG1MGVADatatype.UShort_x4:
                                        controlPointRelativeIndices4 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx4Type = EG1MGVADatatype.UShort_x4
                                case 'JOINTS': # Cache because of the layers
                                    # WIP: Seems to make more sense to do iter_unpack(E+attribute.dataType, data[vbuf.bufferAdress + attribute.offset:vbuf.bufferAdress + attribute.offset + vbuf.count * vbuf.stride]), if not done previously already
                                    jStride = vbuf.stride # WIP: Can probably be improved
                                    jVCount = vbuf.count
                                    if attribute.layer == 0:
                                        jointIdB = data[vbuf.bufferAdress + attribute.offset:]
                                        jointIdBType = attribute.dataType
                                    elif attribute.layer == 1:
                                        jointIdB2 = data[vbuf.bufferAdress + attribute.offset:]
                                        jointIdBType2 = attribute.dataType
                                    if mesh.meshType == 1 and attribute.layer == 0:
                                        controlPointRelativeIndices1 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx1Type = attribute.dataType
                                case 'WEIGHTS':
                                    if attribute.layer == 0:
                                        jointWB = data[vbuf.bufferAdress + attribute.offset:]
                                        jointWBType = attribute.dataType
                                    elif attribute.layer == 1:
                                        jointWB2 = data[vbuf.bufferAdress + attribute.offset:]
                                        jointWB2Type = attribute.dataType
                                    if mesh.meshType == 1 and attribute.layer == 0:
                                        # For some reason, some cloth meshes have a second joint weight set too, only take the first one.
                                        centerOfMassWeightsSet1 = data[vbuf.bufferAdress + attribute.offset:]
                                case 'TANGENT':
                                    if attribute.dataType == EG1MGVADatatype.Float_x4:
                                        if mesh.meshType == 1:
                                            physTanBuffer = data[vbuf.bufferAdress + attribute.offset:]
                                        else:
                                            # rapi.rpgBindTangentBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride)
                                            pass
                                    if attribute.dataType == EG1MGVADatatype.HalfFloat_x4:
                                        if not mesh.meshType == 1:
                                            # rapi.rpgBindTangentBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride)
                                            pass
                                case 'BINORMAL':
                                    if (attribute.dataType == EG1MGVADatatype.Float_x3 or attribute.dataType == EG1MGVADatatype.Float_x4) and mesh.meshType == 1:
                                        controlPointsWeightsSet2 = data[vbuf.bufferAdress + attribute.offset:]
                                case 'COLOR':
                                    if attribute.dataType == EG1MGVADatatype.Float_x3 or attribute.dataType == EG1MGVADatatype.Float_x4:
                                        if mesh.meshType == 1 and attribute.layer == 0:
                                            centerOfMassWeightsSet2 = data[vbuf.bufferAdress + attribute.offset:]
                                        elif bCOLOR and attribute.dataType == EG1MGVADatatype.Float_x3:
                                            # fBuffer = genColor3F(data[vbuf.bufferAdress + attribute.offset:], vbuf.count, vbuf.stride)
                                            # rapi.rpgBindColorBuffer(fBuffer, RPGEODATA_FLOAT?, 16, 4)
                                            pass
                                        elif bCOLOR:
                                            # rapi.rpgBindColorBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_FLOAT?, vbuf.stride, 4)
                                            pass
                                    elif attribute.dataType == EG1MGVADatatype.HalfFloat_x4 and bCOLOR:
                                        # rapi.rpgBindColorBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_HALFFLOAT?, vbuf.stride, 4)
                                        pass
                                    elif attribute.dataType == EG1MGVADatatype.NormUByte_x4 and bCOLOR:
                                        # rapi.rpgBindColorBuffer(data[vbuf.bufferAdress + attribute.offset:], RPGEODATA_UBYTE?, vbuf.stride, 4)
                                        pass
                                case 'FOG':
                                    if attribute.dataType == EG1MGVADatatype.UByte_x4:
                                        controlPointRelativeIndices3 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx3Type = EG1MGVADatatype.UByte_x4
                                    elif attribute.dataType == EG1MGVADatatype.UShort_x4 and bCOLOR:
                                        controlPointRelativeIndices3 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx3Type = EG1MGVADatatype.UShort_x4
                                case 'PSIZE':
                                    if attribute.dataType == EG1MGVADatatype.UByte_x4:
                                        controlPointRelativeIndices2 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx2Type = EG1MGVADatatype.UByte_x4
                                    elif attribute.dataType == EG1MGVADatatype.UShort_x4 and bCOLOR:
                                        controlPointRelativeIndices2 = data[vbuf.bufferAdress + attribute.offset:]
                                        cPIdx2Type = EG1MGVADatatype.UShort_x4
                        # Note: nunMapJointIndex links to the global NUN joint, related with this index, actually the start joint, i.e. parent joint id
                        if mesh.meshType == 1: # and bENABLE_NUNNODES and joints to avoid crashes
                            if -1 < mesh.externalID and mesh.externalID < 10000:
                                # CPSet: modelBone_t = joints + fileIndexToNUNO1Map[i][mesh.externalID]
                                pass
                            elif mesh.externalID < 20000:
                                # CPSet: modelBone_t = joints + fileIndexToNUNV1Map[i][mesh.externalID % 10000]
                                pass
                            elif mesh.externalID < 30000:
                                # t = fileIndexToNUNO3Map[i][mesh.externalID % 10000]
                                # https://github.com/Joschuka/Project-G1M/blob/main/Source/Private/Source.cpp#L1572
                                # CPSet: modelBone_t = joints + t[0] if t[1] < 0 else [joints + t[0] + nunoSubsets[t[1]][ctrl] for ctrl in range(MAX_CTRL_PTS)]
                                # WIP: The latter logic might have to be adjusted, as I don't think the joints object is used correctly
                                pass
                            # WIP: Maybe parse mesh.meshType == 1 attributes here instead?
                            jointWBFinal = bytes(16 * phys1Count)
                            jointIBFinal = bytes(8 * phys1Count)
                            dstIS = [0] * 4 * phys1Count
                            dstIB = [0] * 8 * phys1Count
                            dstW = [0.0] * 4 * phys1Count # or [(0.0, 0.0, 0.0, 0.0) for _ in range(phys1Count)]
                            # for vbi in range(0, phys1Count * phys1Stride, phys1Stride):
                            for j in range(phys1Count):
                                vbi = phys1Stride * j # if vbuf.stride % 16 == 0
                                # WIP: Need shorter names or parsed 4f data that can be retrieved with the respective index
                                # The latter might be better, since vbuf.bufferAdress + attribute.offset might not be accurate to the 'data' buffer
                                controlPCMWVec1 = unpack_from(E+'4f', data, controlPointsWeightsSet1 + vbi) # Used for "horizontal" alignment with CPs on the same line, kind of?
                                controlPCMWVec2 = unpack_from(E+'4f', data, controlPointsWeightsSet2 + vbi)
                                centerOfMassWVec1 = unpack_from(E+'4f', data, centerOfMassWeightsSet1 + vbi) # Used for "vertical" alignment, to determine along the previously computed horizontal positions
                                centerOfMassWVec2 = unpack_from(E+'4f', data, centerOfMassWeightsSet2 + vbi)
                                if cPIdx1Type == EG1MGVADatatype.UByte_x4:
                                    indexPointer = unpack_from(E+'4B', controlPointRelativeIndices1, vbi) # WIP: Can be vastly improved
                                    # m1 = RichMat43(
                                    #   CPSet[indexPointer[0]].mat.o,
                                    #   CPSet[indexPointer[1]].mat.o,
                                    #   CPSet[indexPointer[2]].mat.o,
                                    #   CPSet[indexPointer[3]].mat.o,
                                    # )
                                    # u1 = m1.GetTranspose().TransformVec4(controlPCMWVec1).ToVec3()
                                    # v1 = m1.GetTranspose().TransformVec4(controlPCMWVec2).ToVec3()
                                elif cPIdx1Type == EG1MGVADatatype.UShort_x4: # WIP: Ushort always little endian?
                                    # identical except for indexPointer
                                    indexPointer = (0 if p == 65535 else p for p in unpack(E+'4H', controlPointRelativeIndices1[vbi:vbi + 8])) # is this necessary? can i use 65535 for unused weight in Python/Blender?
                                # identical except using for controlPointRelativeIndices2 and uv2
                                if cPIdx2Type == EG1MGVADatatype.UByte_x4:
                                    indexPointer = unpack(E+'4B', controlPointRelativeIndices2[vbi:vbi + 4])
                                elif cPIdx1Type == EG1MGVADatatype.UShort_x4:
                                    indexPointer = (0 if p == 65535 else p for p in unpack(E+'4H', controlPointRelativeIndices2[vbi:vbi + 8]))
                                # identical except using for controlPointRelativeIndices3 and uv3
                                if cPIdx2Type == EG1MGVADatatype.UByte_x4:
                                    indexPointer = unpack(E+'4B', controlPointRelativeIndices3[vbi:vbi + 4])
                                elif cPIdx1Type == EG1MGVADatatype.UShort_x4:
                                    indexPointer = (0 if p == 65535 else p for p in unpack(E+'4H', controlPointRelativeIndices3[vbi:vbi + 8]))
                                # identical except using for controlPointRelativeIndices4 and uv4
                                if cPIdx2Type == EG1MGVADatatype.UByte_x4:
                                    indexPointer = unpack(E+'4B', controlPointRelativeIndices4[vbi:vbi + 4])
                                elif cPIdx1Type == EG1MGVADatatype.UShort_x4:
                                    indexPointer = (0 if p == 65535 else p for p in unpack(E+'4H', controlPointRelativeIndices4[vbi:vbi + 8]))
					            # The b and c cross product gives the direction that the point needs to be extruded in, from the driver shape.
					            # The depth buffer gives the distance from the driver, a is the "base position".
                                # a = RichMat43(u1, u2, u3, u4).GetTranspose().TransformVec4(centerOfMassWVec1).ToVec3()
                                # b = RichMat43(u1, u2, u3, u4).GetTranspose().TransformVec4(centerOfMassWVec2).ToVec3()
                                # c = RichMat43(v1, v2, v3, v4).GetTranspose().TransformVec4(centerOfMassWVec1).ToVec3()
                                depth, = unpack(E+'f', depthFromDriver[vbi + 12:vbi + 16]) # did I get this right?
                                # Assume that NUNO normals and tangents are always float (might be half float, but not supported)
                                # normalCoords = RichVec3(unpack(E+'3f', depthFromDriver[vbi:vbi + 12])) if depthFromDriver else RichVec3()
                                # tanCoords = RichVec3(unpack(E+'3f', physTanBuffer[vbi:vbi + 12])) if physTanBuffer else RichVec3()
                                bHasSkinnedParts = len(c) == 0
                                if (bHasSkinnedParts):
                                    # transformPosF(data[controlPointsWeightsSet1 + vbi:controlPointsWeightsSet1 + vbi + 16], 1, phys1Stride, (joints + nunMapJointIndex[index]).eData.parent.mat))
                                    bHasSkinnedParts = True
                                    dstW[4 * j:4 * j + 4] = centerOfMassWVec1[:4]
                                    if cPIdx1Type == EG1MGVADatatype.UByte_x4:
                                        dstIB[4 * j:4 * j + 4] = unpack('< 4B', controlPointRelativeIndices1[vbi:vbi + 4])
                                    elif cPIdx1Type == EG1MGVADatatype.UShort_x4:
                                        dstIS[4 * j:4 * j + 4] = unpack('< 4H', controlPointRelativeIndices1[vbi:vbi + 8])
                                    if depthFromDriver:
                                        # g_mfn.Math_TransformPointByMatrixNoTrans((joints + nunMapJointIndex[smIdx]).eData.parent.mat, normalCoords.v, tmp)
                                        # g_mfn.Math_VecCopy(tmp, normalCoords.v) # + normalCoords.ChangeEndian()
                                        # g_mfn.Math_VecCopy(normalCoords.v, unpack(E+'3f', depthFromDriver[vbi:vbi + 12]))
                                        pass
                                else:
                                    # d = b.Cross(c)
                                    if depthFromDriver:
                                        # normalCoords = b * normalCoords.v[1] + c * normalCoords.v[0] + d * normalCoords.v[2]
                                        # normalCoords.Normalize()
                                        pass
                                    if physTanBuffer:
                                        # tanCoords = b * tanCoords.v[1] + c * tanCoords.v[0] + d * tanCoords.v[2]
                                        # tanCoords.Normalize()
                                        pass
                                    if bIsNUNO5Global:
                                        # d = d.Normalized() # or d.Normalize()
                                        pass
                                    c = d * depth + a
                                    # change endian of the coordinates now? I don't get the reason behind this. But it's probable that calculations don't work if endian is changed before.
                                    # g_mfn.Math_VecCopy(c.v, unpack(E+'3f', controlPointsWeightsSet1[vbi:vbi + 12]))
                                    # if physTanBuffer: g_mfn.Math_VecCopy(tanCoords.v, unpack(E+'3f', physTanBuffer[vbi:vbi + 12]))
                                    # if depthFromDriver: g_mfn.Math_VecCopy(normalCoords.v, unpack(E+'3f', depthFromDriver[vbi:vbi + 12]))
                        elif mesh.meshType == 2 and jStride > 0: # and joints to avoid crashes # Cloth type 2 or SOFT? (WIP)
                            attribute = g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes[0]
                            for j in range(g1mg.vertexBuffers[attribute.bufferID].count):
                                bPID = unpack('< 4B', jointIdB[j * jStride:j * jStride + 4]) if jointIdBType == EG1MGVADatatype.UByte_x4 else \
                                    unpack('< 4H', jointIdB[j * jStride:j * jStride + 8]) if jointIdBType == EG1MGVADatatype.UShort_x4 else \
                                    unpack('< 4I', jointIdB[j * jStride:j * jStride + 16]) if jointIdBType == EG1MGVADatatype.UInt_x4 else 0
                                bPID //= 3
                                if bPID and bPID < len(g1mg.jointPalettes[submesh.bonePaletteIndex].entries):
                                    # See 0xb2e220c4/0x7c68948e from wolong. Implicit parenting to another internal skel or unneeded transformation?
                                    jID = g1mg.jointPalettes[submesh.bonePaletteIndex].entries[bPID].physicsIndex ^ 0x80000000 # ^ 0x80000000 external skel only?
                                    # matrix: modelMatrix_t = joints[jID].mat
                                    # Here we assume that the first internal skel has the physics joint's parent (which is always the case on all the samples)
                                    # transformPosF(posB[j * jStride:], 1, jStride, joints[jID].mat)
                            # rapi.rpgBindPositionBuffer(posB, RPGEODATA_FLOAT, jStride)
                        if mesh.meshType != 1 and jVCount > 0: # and joints to avoid crashes
                            jidCount = 8 if jointIdB2 else 4
                            # Annoying edge cases :
                            # - only bone indices. Assign first weight to 1 and zero out the other components (done in skin function)
                            # - boneIndex and weight first layers, boneIndex 2nd layer but no weight 2nd layer. Zero out the latter in that case (done in skin function)
                            if jointIdBType == EG1MGVADatatype.UByte_x4:
                                # rapi.rpgBindBoneIndexBuffer(jointIdB, RPGEODATA_UBYTE, jStride, jidCount)
                                pass
                            elif jointIdBType == EG1MGVADatatype.UShort_x4:
                                # rapi.rpgBindBoneIndexBuffer(jointIdB, RPGEODATA_USHORT, jStride, jidCount)
                                pass
                            elif jointIdBType == EG1MGVADatatype.UInt_x4:
                                # rapi.rpgBindBoneIndexBuffer(jointIdB, RPGEODATA_UINT, jStride, jidCount)
                                pass
                            if jointWBType == EG1MGVADatatype.Float_x4 and (jointWB2Type == EG1MGVADatatype.Float_x4 or (jointWB2Type == EG1MGVADatatype.Dummy and not jointIdB2)): # jointIdB2: edge case
                                # rapi.rpgBindBoneWeightBuffer(jointWB, RPGEODATA_FLOAT, jStride, jidCount)
                                pass
                            elif jointWBType == EG1MGVADatatype.HalfFloat_x4 and (jointWB2Type == EG1MGVADatatype.HalfFloat_x4 or (jointWB2Type == EG1MGVADatatype.Dummy and not jointIdB2)): # jointIdB2: edge case
                                # rapi.rpgBindBoneWeightBuffer(jointWB, RPGEODATA_HALFFLOAT, jStride, jidCount)
                                pass
                            elif jointWBType == EG1MGVADatatype.NormUByte_x4 and (jointWB2Type == EG1MGVADatatype.NormUByte_x4 or (jointWB2Type == EG1MGVADatatype.Dummy and not jointIdB2)): # jointIdB2: edge case
                                # rapi.rpgBindBoneWeightBuffer(jointWB, RPGEODATA_UBYTE, jStride, jidCount)
                                pass
                            else:
                                # jointWBFinal = skinSMeshW(jointWB, jointWBType, jointWB2, jointWB2Type, jVCount, jStride, jointIdB2)
                                # rapi.rpgBindBoneWeightBuffer(jointWBFinal, RPGEODATA_FLOAT, jidCount * 4, jidCount)
                                pass
                        if submesh.submeshType & 0x2: # 63, e.g. 79d40f50.g1m from SoP
                            size = g1mg.vertexBuffers[g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes[0].bufferID].count
                            # rapi.rpgBindBoneIndexBuffer(jointIBFinal, RPGEODATA_UBYTE, 1, 1) # need to resize jointIBFinal?
                            # rapi.rpgBindBoneWeightBuffer(jointWBFinal, RPGEODATA_UBYTE, 1, 1) # need to resize jointWBFinal?
                        if jointMap: pass # rapi.rpgSetBoneMap(jointMap)
                        if submesh.indexBufferPrimType == 3:
                            # rapi.rpgCommitTriangles(data[ibuf.bufferAdress + submesh.indexBufferOffset * ibuf.bitwidth:], ibuf.dataType, submesh.indexCount, RPGEO_TRIANGLE, 1)
                            pass
                        elif submesh.indexBufferPrimType == 4:
                            # rapi.rpgCommitTriangles(data[ibuf.bufferAdress + submesh.indexBufferOffset * ibuf.bitwidth:], ibuf.dataType, submesh.indexCount, RPGEO_TRIANGLE_STRIP, 1)
                            pass

    # Noesis stuff: Feeding driver meshes
    # rapi.rpgSetOption(RPGOPT_BIGENDIAN, false)
	# rapi.rpgClearBufferBinds()
	# rapi.rpgSetBoneMap(nullptr)
    dvmIndex = 0
    
    # Noesis stuff: Joints and anims
    if joints:
		# rapi.rpgSetExData_Bones(joints, jointIndex)
		# anims: noesisAnim_t = rapi.Noesis_AnimFromAnimsList(animList, len(animList))
		# if anims: rapi.rpgSetExData_AnimsNum(anims, 1)
		# if not bDisableNUNNodes and bEnableNUNAutoRig:
		# 	rapi.rpgSetOption(RPGOPT_FILLINWEIGHTS, true)
		# else:
		# 	rapi.rpgSetOption(RPGOPT_FILLINWEIGHTS, false)
        pass

    # Noesis stuff: Materials
	# pMd: noesisMatData_t = rapi.Noesis_GetMatDataFromLists(matList, textureList)
	# if pMd: rapi.rpgSetExData_Materials(pMd)
    
    # Noesis stuff: Model
    # mdl: noesisModel_t = rapi.rpgConstructModel()
    if mdl:
        numMdl = 1
    elif joints:
        # workaround, if has skeleton but no geometry
        # rapi.rpgSetExData_Bones(joints, jointIndex)
        # dst = [g_mfn.Math_TransformPointByMatrix(joints[i].mat, (0, 0, 0)) for i in enumerate(jointIndex)]
        # etc., continue adding a dummy mesh for Noesis
        # if mdl: numMdl = 1
        pass

    # SetPreviewAnimSpeed(framerate)

globalIndices = [] # WIP: ? Use1: Disabled Nuns but can be better done in Python
globalIndexToLayers = {} # WIP: ?
globalToFinal = {} # WIP: ?
INTERNAL_ID_FALLBACK = None

def T(data: bytes, G1Tpaths: list[Path]):
    bHasParsedG1MS = False # WIP: global?
    jointIndex = 0 # WIP: global?
    # Temp: skeldata = []
    magic = data[:4] # do nothing with version and size
    if magic == b'G1M_': E == '>'
    elif magic[::-1] == b'G1M_': E == '<' # Set explicitly, in case multiple files are processed with different endian
    else: return None
    for _ in range(g1mHeader.chunkCount):
        header = GResourceHeader(*unpack_from(E+'4s2I', data, pos)) # do nothing with version
        magic = GUST_MAGICS[header.magic] if E == '<' else header.magic.decode()
        # if magic == 'G1MG':
        #   WIP: append data buffer or offset to G1MGs? It seems like all data, esp skel must be read beforehand
        if magic == 'G1MM':
            G1MMs.append(G1MM(data, pos)) # WIP: No code to rely on
        elif magic == 'G1MS' and not bHasParsedG1MS:
            skel = G1MS(data, pos, header.chunkVersion)
            # WIP: Could name bones now, if OID exists, but it's probably better to add skel to a structure and then name them
            if skel.bIsInternal:
                SKELETON_INTERNAL_INDEXP1 += 1
                if not INTERNAL_ID_FALLBACK: INTERNAL_ID_FALLBACK = skel.localIDToGlobalID
                # WIP: temp calc_abs_skeleton translate (if possible, do only when building the skel structure)
                for i, bone in enumerate(skel.joints):
                    if bone.parentID < 0: # root bone as absolute origin
                        skel.joints[i].abs_tm = Quaternion(skel.joints[i].rotation).transformation_matrix
                        skel.joints[i].abs_tm[3] = *skel.joints[i].position, 1
                    else:
                        parent_bone = next(j for i, j in enumerate(skel.joints) if i == bone.parentId) # that's where the toglobal list/dict comes in handy
                        skel.joints[i].abs_tm = calc_abs_rotation_position(bone, parent_bone)
                bHasParsedG1MS = True # WIP: Needs to be internal, if external, need additional G1M files for skeleton which would then include internal skel. But probably just read all skeletons and build structure from all joints (if possble).
            else:
                SKELETON_LAYER += 1 # WIP: Might need layer for all skeletons, if following the build skel logic from all files
            # WIP: It might be better to process layers later
            # count internalSkeletons (0, 1, more)
            # skeletons.append(skel) ?? see below
            # Note: The Noesis script makes tables to know which skeleton (by index) is internal
            for k, v in skel.globalIDToLocalID.items():
                if not skel.bIsInternal:
                    if k in globalIndexToLayers:
                        if SKELETON_LAYER not in globalIndexToLayers[k]:
                            globalIndexToLayers[k].append(SKELETON_LAYER)
                            del skel.globalIDToLocalID[k]
                            k += SKELETON_LAYER * 1000
                            skel.globalIDToLocalID[k] = v
                            skel.localIDToGlobalID[v] = k
                    else:
                        globalIndexToLayers[k] = [SKELETON_LAYER]
                if k not in globalIndices:
                    globalIndices.append(k) # WIP: or use dict? globalIndices[k] = v
                    globalToFinal[skel.localIDToGlobalID[v]] = jointIndex
                    skel.jointLocalIndexToExtract.append(v)
                    # Note: Can only process skeletons after finding all!
            G1MSs.append(skel) # WIP (duplicate): The skeltons should probably read beforehand, even if only using one skeleton
        elif bENABLE_NUNNODES: # fileID is important? WIP: Try with single files first, then start using fileID code, if multiple files makes sense
            if magic == 'NUNO': # fileID is important? WIP: Try with single files first, then start using fileID code, if multiple files makes sense
                NUNOs.append(NUNO(data, pos)) # WIP: append or process?
            elif magic == 'NUNV': # fileID is important?
                NUNVs.append(NUNV(data, pos)) # WIP: append or process?
            elif magic == 'NUNS': # fileID is important?
                NUNSs.append(NUNS(data, pos)) # WIP: append or process?
            elif magic == 'SOFT': # fileID is important?
                SOFTs.append(SOFT(data[pos:pos + header.chunkSize])) # WIP: append or process?
            # WIP: eArmada8's script only carries max. one for each nun type
        pos += header.chunkSize
    if (bMERGE or bMERGEG1MONLY) and bG1TMERGEG1MONLY: # WIP: Options incomplete
        # WIP: Do we need a dialogue? I think this should be handled by the argument parser.
        # Blender might have an option to pick various additional files
        # if internalSkeletons > 0 (if internalSkeletons): for each internalSkeletons load G1T
        # if len(G1Tpaths) < internalSkeletons (count): 
        #    raise ValueError(f'{ns} textures expected, {nt} provided.')
        pass
    # Building skeleton if any internal ones
    # It seems like it's not possible to process geometry (G1MS) without an actual skeleton (ext. skel are references to ext. skels that are marked as internal)
    if SKELETON_INTERNAL_INDEXP1:
        for s in G1MSs:
            # WIP: Parsing in file order, giving a different jointIndex than the Noesis plugin would give.
            # But leaving the loop here, in case it should be changed.
            # for s in [sk for sk in skeletons if sk.bIsInternal]:
            G1MS_Process(s, jointIndex)
            # Color 1
        # WIP: Nun meshes should be read before reading submeshes?
        # WIP: The calc_nun_maps doesn't look good to me and seems to return some data that I might not need. But part of the calculations might be helpful
        # WIP: For NUNOs, etc, could add their entries (NUNO1, etc.) in a one dimensional list?
        # nun_maps = calc_nun_maps(stack_nun(NUNOs, NUNSs, NUNVs), model_skel_data)
        for i, n in enumerate(NUNOs):
            for nun1 in n.Nuno1:
                jointStart = jointIndex
                nunParentJointID = globalToFinal[(nun1.parentID ^ 0x80000000 if nun1.parentID >> 31 else nun1.parentID)]
                # WIP: Is the id important later on?
                # fileIndexToNUNO1Map[NUNOFileIDs[i]].append(jointIndex)
                # Prepare driverMeshes (Noesis):
                # createDriverVertexBuffers(dMesh: mesh_t, len(nun1.controlPoints), unpooledBufs, rapi)
                # ...
                polys = []
                # Process control points
                for j, p in enumerate(nun1.controlPoints):
                    # WIP: p is tuple of 4 floats, that need to become a vec3
                    link = nun1.influences[j]
                    parentID = link.P3
                    if parentID == 0xFFFFFFFF:
                        parentID = nunParentJointID
                        # jointMatrix = RichQuat().ToMat43().GetInverse().m
                        # g_mfn.Math_VecCopy(p (vec3) .v, jointMatrix.m.o)
                    else:
                        parentID += jointStart
                        # WIP: Matrix calculations, need to be positioned in relation to the parent (main skeleton)
                        # mat1 = RichMat43(joints[nunParentJointID].mat)
                        # mat2 = RichMat43(joints[parentID].mat)
                        # jointMatrix = mat1 * mat2.GetInverse()
                        # p = jointMatrix.TransformPoint(p)
                        # g_mfn.Math_VecCopy(p.v, jointMatrix.m.o)
                    # Noesis:
                    # mat3 = RichMat43(joints[parentID].mat)
                    # joint.name = f'nuno1_p_{nunParentJointID}_bone_{jointIndex}'
                    # ...
                    # Driver mesh:
                    # works with buffers, but structure is difficult to understand (writes into Noesis buffer?). Is this key to the shared influences?
                    # mat4 = RichMat43(joints[jointIndex].mat)
                    if link.P1 > 0 and link.P3 > 0: polys.append((j, link.P1, link.P3))
                    if link.P2 > 0 and link.P4 > 0: polys.append((j, link.P2, link.P4))
                    jointIndex += 1
                # Now to create/update a mesh/vertices with the polys, etc.
                # driverMeshes.append(dMesh)
            # Color 2 (both/all)
            for nun3 in n.Nuno3n5:
                if nun3.parentSetID > -1: # NUNO5
                    # bNUNO5HasSubsets = True WIP: Prevents Noesis crash with multiple sub-sets
                    jointStart = fileIndexToNUNO3Map[NUNOFileIDs[i]][nun3.parentSetID][1] # WIP: Is there a better way in Python? If not, fileIndexToNUNO3Map and NUNOFileIDs need to be global, but should probably be simplified (nunIndexToNUNO3Map[i][nun3.parentSetID])
                    # fileIndexToNUNO3Map[NUNOFileIDs[i]].append((jointStart, len(nunoSubsets)))
                    # If possible, combine it with the follwing:
                    # nunoSubsets.append(subset)
                    # Theoretically has a max size of MAX_CTRL_PTS, but what if nuno5 subset is larger?
                    nunoSubsets.append((nun3.influences[j].P1 for j in range(len(nun1.controlPoints)))) # WIP: Do we really need to append another one instead of processing it right here?
                else: # identical to nun1, except for (parentID == 0xFFFFFFFF & else) calculations and fileIndexToNUNO3Map
                    # WIP: Really need a better way to go about this (NUN stuff is per file but not the other stuff?):
                    # fileIndexToNUNO3Map[NUNOFileIDs[i]].append((jointStart, -1))
                    # WIP: Don't process unknown part, if bIsNUNO5Global and link.P5 == 0 (see 79d40f50 from SoP, 7c68948e from WoLong)
                    # joint.name = f'nuno3_p_{nunParentJointID}_bone_{jointIndex}' WIP: would eventually need a version for nuno5
                    pass # again, mostly same as nuno1
        for i, n in enumerate(NUNVs):
            for nun1 in n.Nunv1:
                # Identical to Nuno1 nun1, with fileIndexToNUNV1Map
                # joint.name = f'nunv1_p_{nunParentJointID}_bone_{jointIndex}'
                pass
        for i, n in enumerate(NUNSs):
            for nun1 in n.Nuns1:
                # Identical to Nuno1 nun1, without fileIndexToNUNV1Map ??
                # joint.name = f'nuns1_p_{nunParentJointID}_bone_{jointIndex}'ID = s.localIDToGlobalID[idx]
                pass
        # WIP: SOFT ?? https://github.com/Joschuka/Project-G1M/blob/main/Source/Private/Source.cpp#L1010

def G1MS_Process(s: G1MS, jointIndex: int):
    """ WIP: Layering external skeletons (but could probably be simplified a lot) or use combine_skeleton
        No need for jointLocalIndexToExtract, as building the skeleton can check for existing bones on the fly.
        should it be globalIndices.append(k + (SKELETON_LAYER if skel.bIsInternal else 0) * 1000) ?
        ^^ could even use this instead of globalIndexToLayers, probably
    # count internalSkeletons (0, 1, more)
    SKELETON_LAYER += 1
    for k, v in skel.globalIDToLocalID.items():
        if not skel.bIsInternal:
            if k in globalIndexToLayers:
                if SKELETON_LAYER not in globalIndexToLayers[k]:
                    globalIndexToLayers[k].append(SKELETON_LAYER)
                    del skel.globalIDToLocalID[k]
                    k += SKELETON_LAYER * 1000
                    skel.globalIDToLocalID[k] = v
                    skel.localIDToGlobalID[v] = k
            else:
                globalIndexToLayers[k] = [SKELETON_LAYER]
        if k not in globalIndices:
            globalIndices.append(k)
            globalToFinal[skel.localIDToGlobalID[v]] = jointIndex
            skel.jointLocalIndexToExtract.append(v)
            # Note: Can only process skeletons after finding all!
    """

    for idx in s.jointLocalIndexToExtract:
        G1MS_Joint_Process(s, idx, jointIndex)
        # Noesis:
        # joint: modelBone_t = joints + jointIndex ??
        # joint.index = jointIndex
        parent = s.joints[idx].parentID
        if s.bIsInternal:
            if parent >> 31: # >= 0x80000000
                parent = INTERNAL_ID_FALLBACK[parent]
        elif parent == 0xFFFFFFFF:
            parent = None
            if s.joints[idx].position[0] + s.joints[idx].position[1] + s.joints[idx].position[2]:
                bIsSkeletonOrigin = False # hack, might find a better way (at least for the variable)
                s.joints[idx].position = (0.0, 0.0, 0.0)
        else:
            parent = s.localIDToGlobalID[parent]
        if not IS_G1MS_UNORDERED: parent = globalToFinal[parent]
        ID = s.localIDToGlobalID[idx]
        name = GLOBAL2OID[ID] if ID in GLOBAL2OID else f'{'bone_' if s.bIsInternal else 'physbone_'}{ID}'
        # WIP: Joints must also have the jointIndex (indexed list/tuple, etc.)
        # Noesis:
        # joint.eData.parent = joints + parent
        # joint.name = name
        # WIP: Build Matrix
        # joint.mat = s.joints[idx].rotation.ToMat43().GetInverse().m !!!
        #       an empty one: jointMatrix = RichQuat().ToMat43().GetInverse().m
        # g_mfn.Math_VecCopy(s.joints[idx].position, joint.mat.o)
        # WIP: Give joint a color (same for internal and external
        jointIndex += 1

"""WIP: G1M2glTF notes:
- TRANSFORM_CLOTH_MESH = True
"""

def convert_bones_to_single_file(gltf_data: dict, g1mg: G1MG) -> dict:
    bone_element_indices =[x for x in submesh['fmt']['elements'] if x['SemanticName'] == 'BLENDINDICES']
    if len(bone_element_indices) > 0:
        for i in range(len(bone_element_indices)):
            bone_element_index = int(bone_element_indices[i]['id'])
            for j in range(len(submesh['vb'][bone_element_index]['Buffer'])):
                for k in range(len(submesh['vb'][bone_element_index]['Buffer'][j])):
                    # Dunno why G1M indices count by 3, I think it's for NUN?
                    submesh['vb'][bone_element_index]['Buffer'][j][k] = \
                        int(submesh['vb'][bone_element_index]['Buffer'][j][k] // 3) 
    return(submesh)

def write_glTF(s: G1MS, g1mg: G1MG, data: bytes, output_file: Path, keep_color: bool):
    # Could support multiple scenes in the future
    # has/needs duplicate code
    global bTRANSLATE_MESHES
    # WIP: Could use multiple skeletons and layers?
    # Note: This raises an exception, if parent hasn't been updated before the child
    for i, bone in enumerate(s.joints):
        if bone.parentID != 0xFFFFFFFF and bone.parentID < len(s.joints):
            s.joints[i].abs_tm = calc_abs_rotation_position(bone, s.joints[bone.parentID])
    # temp: duplicate nun stuff
    gltf_data = {
        'asset': { 'version': '2.0' },
        'accessors': [],
        'bufferViews': [],
        'buffers': [],
        'images': [],
        'materials': [],
        'meshes': [],
        'nodes': [],
        'samplers': [],
        'scenes': [{ 'nodes': [0] }],
        'scene': 0,
        'skins': [],
        'textures': []
    }
    bin_data = bytes()
    buffer_view = 0

    if g1mg.materials:
        idx = 0
        g1tj = Path('g1t.json')
        if g1tj.exists():
            with g1tj.open(encoding='UTF-8') as jf:
                gltf_data['images'] = [{'uri': x['name']} for x in json.load(jf)['textures']] # WIP: str(int(x['name'], 16)) | g1t_data = json.load(jf)
        else:
            # Making an assumption here that all images are the number and .dds, since g1t.json is not available
            gltf_data['images'] = [{'uri': f'{str(i).zfill(3)}.dds'} for i in range(max(x.index for y in g1mg.materials for x in y.g1mgTextures) + 1)]
        for i, mat in enumerate(g1mg.materials):
            material = {'name': f'Material_{i:02d}'}
            for j, tex in enumerate(mat.g1mgTextures):
                gltf_t = {'index' : idx, 'texCoord': tex.layer}
                if tex.textureType == 1:
                    material['pbrMetallicRoughness'] = {
                        'baseColorTexture': gltf_t,
                        'metallicFactor' : 0.0,
                        'roughnessFactor' : 1.0
                    }
                elif tex.textureType == 3:
                    material['normalTexture'] = gltf_t
                elif tex.textureType == 5:
                    material['occlusionTexture'] = gltf_t
                elif tex.textureType == 2:
                    material['emissiveTexture'] = gltf_t
                gltf_data['samplers'].append({'wrapS': 10497, 'wrapT': 10497}) # It seems like wrap is the only type used, according to THRG?
                gltf_data['textures'].append({'source': tex.index, 'sampler': idx })
                idx += 1
            gltf_data['materials'].append(material)

    for i, bone in enumerate(s.joints):
        # WIP: Can't have NUN bones? There's no reason for it to fail, so i is used instead of len(gltf_data['nodes'])
        node = {'children': [], 'name': f'bone_{s.getGlobalID(i)}'}
        if bone.rotation != (1, 0, 0, 0): node['rotation'] = (bone.rx, bone.ry, bone.rz, bone.rw)
        if bone.scale != (1, 1, 1): node['scale'] = bone.scale
        if bone.position != (0, 0, 0): node['translation'] = bone.position
        if i > 0: gltf_data['nodes'][bone.parentID]['children'].append(i)
        gltf_data['nodes'].append(node)
    bc = i + 1
    for i in range(bc):
        if not gltf_data['nodes'][i]['children']: del(gltf_data['nodes'][i]['children'])

    for subindex, submesh in enumerate(g1mg.submeshes):
        print(f'Processing submesh {subindex}...')
        # Only process 3D submeshes, unless NUN data is available
        # WIP: or len(position_data[0]) == 3 | WIP2: could one use [x[:3] for x in position_data] ?
        if next(x.dataType for x in g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes if x.semantic == 'Position')[0] == '3': # WIP: or NUN available
            submesh_lod = next(x for y in g1mg.meshGroups for x in y.meshes if subindex in x.indices)
            # WIP:
            # look in write_submeshes
            # submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata, model_skel_data, fmts, e=e, cull_vertices = True, preserve_trianglestrip = True)
            # cloth render pattern, but with submesh_lod...
            # if len(ib) > 0
            blend_indices = list(g1mg.get_vb(submesh.vertexBufferIndex, 'JointIndex', data)) # WIP Note: All values should be // 3 (something to do with triangles?)
            skin_weights = list(g1mg.get_vb(submesh.vertexBufferIndex, 'JointWeight', data))
            swf = next(x.dataType for x in g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes if x.semantic == 'JointWeight')
            if skin_weights:
                d = len(blend_indices[0]) > len(skin_weights[0]) # if there aren't enough weight values, they should be expanded | WIP: Numpy could be helpful once again
                if d > 0:
                    swf = f'{len(blend_indices[0])}f' # prefices = ['R','G','B','A','D']
                    for _ in range(d):
                        for i, sw in enumerate(skin_weights):
                            w = 1 - sum(sw)
                            skin_weights[i] = sw + (0 if w < 0.00001 else w,)
            # WIP: Remove cloth weights: for i, sw in enumerate(skin_weights): (if sw[0] != max(sw), probably): skin_weights[i] = (1,) + sw[1:] and skin_weights[i] = tuple(0 for _ in range(len(sw)))
            #      But why would I add cloth weights to begin with?
            if submesh_lod.meshType != 0: # cloth
                for i, t in enumerate(tangent_data):
                    tangent_data[i] = tuple(t[:3] / np.linalg.norm(t[:3])) + t[3:]
            # Move model to root node if bTRANSLATE_MESHES set to True
            if bTRANSLATE_MESHES and 'translation' in gltf_data['nodes'][0]:
                position_veclength = len(position_data[0]) # should be at least 3
                shift = np.array(gltf_data['nodes'][0]['translation'] + (0,) * (position_veclength - 3))
                position_data = [tuple(p + shift) for p in position_data]
            primitive = {"attributes":{}}
            block_offset = len(bin_data)
            for i, a in enumerate(g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes): # is the order correct?
                if a.semantic == 'COLOR' and not keep_color: continue # or remove from primitive["attributes"] afterwards
                if a.semantic == 'WEIGHTS':
                    if not skin_weights: continue
                    a.dataType = swf
                vbe = g1mg.vertex_buffers[g1mg.vertexAttributeSets[submesh.vertexBufferIndex].vBufferIndices[a.bufferID]]
                vb = position_data if a.semantic == 'POSITION' else \
                    tangent_data if a.semantic == 'TANGENT' else \
                    blend_indices if a.semantic == 'JOINTS' else \
                    skin_weights if a.semantic == 'WEIGHTS' else \
                    list(unpack_from(f'{E} {a.dataType}', data, p) for p in range(vbe.offset + a.offset, vbe.offset + a.offset + vbe.count * vbe.stride, vbe.stride)) # WIP: duplicate code, in case there are problems
                if a.dataType not in STRUCT_TO_GLTF_TYPE: a.dataType = f'{a.dataType[0]}f' if a.dataType[0].isdigit() else f'{len(a.dataType)}f'
                gltf_type = STRUCT_TO_GLTF_TYPE[a.dataType]
                sem = f'{a.semantic}_{i}' if a.semantic in ('WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD') else a.semantic
                byte_length = vbe.count * calcsize(a.dataType)
                primitive["attributes"][sem] = len(gltf_data['accessors'])
                gltf_data['accessors'].append({
                    'bufferView' : buffer_view,
                    'componentType': gltf_type[1],
                    'count': vbe.count, # or better len() ?
                    'type': gltf_type[0]
                })
                if a.semantic == 'Position':
                    gltf_data['accessors'][-1]['max'] = tuple(max(v) for v in zip(*position_data))
                    gltf_data['accessors'][-1]['min'] = tuple(min(v) for v in zip(*position_data))
                gltf_data['bufferViews'].append({
                    'buffer' : 0,
                    'byteOffset': block_offset,
                    'byteLength': byte_length
                })
                # Endian? | Could there be a straight buffer copy without struct?, But can't convert unsupported formats, then
                bin_data += pack(f'{E} {a.dataType * vbe.count}', *sum(vb, ())) # WIP: Must all be tuples
                block_offset += byte_length
                buffer_view += 1
            ib = g1mg.index_buffers[submesh.indexBufferIndex]
            if ib.dataType not in STRUCT_TO_GLTF_TYPE: a.dataType = 'I'
            gltf_type = STRUCT_TO_GLTF_TYPE[a.dataType]
            primitive["indices"] = len(gltf_data['accessors'])
            gltf_data['accessors'].append({
                'bufferView' : buffer_view,
                'componentType': gltf_type[1],
                'count': ib.count,
                'type': gltf_type[0]
            })
            if a.semantic == 'Position':
                gltf_data['accessors'][-1]['max'] = tuple(max(v) for v in zip(*position_data))
                gltf_data['accessors'][-1]['min'] = tuple(min(v) for v in zip(*position_data))
            gltf_data['bufferViews'].append({
                'buffer' : 0,
                'byteOffset': block_offset,
                'byteLength': ib.count * ib.bitwidth,
                'target': 34963
            })
            bin_data += data[ib.offset:ib.count * ib.bitwidth]
            buffer_view += 1
            # ib = unpack_from(f'{E} {ib.count}{ib.dataType}', data, ib.offset)

            primitive["mode"] = 4 if submesh.indexBufferPrimType == 3 else \
                                5 if submesh.indexBufferPrimType == 4 else \
                                0
            if submesh.materialIndex < len(gltf_data['materials']):
                primitive["material"] = submesh.materialIndex
            gltf_data['nodes'].append({
                'mesh': subindex,
                'name': f'Mesh_{subindex}'
            })
            gltf_data['meshes'].append({
                'primitives': [primitive],
                'name': f'Mesh_{subindex}'
            })

            if s.bIsInternal and s.header.jointCount > 1 and skin_weights and submesh_lod.meshType == 2:
                gltf_data['nodes'][-1]['skin'] = len(gltf_data['skins'])
                inv_mtx_buffer = bytes()
                skin_bones = []
                for i, j in enumerate(g1mg.joint_palettes[submesh.bonePaletteIndex].joints):
                    skin_bones.append(j.jointIndex) # WIP: Is this global or local? I need global (i.e. the bone's index)
                    mtx = s.getJoint(j.jointIndex).abs_tm # WIP: Is this global or local?
                    inv_mtx_buffer += pack(E+'16f', *ndarray.transpose(np.linalg.inv(mtx)).flatten())
                gltf_data['skins'].append({
                    'inverseBindMatrices': len(gltf_data['accessors']),
                    'joints': skin_bones
                })
                gltf_data['accessors'].append({
                    'bufferView' : buffer_view,
                    'componentType': 5126,
                    'count': i + 1,
                    'type': 'MAT4'
                })
                gltf_data['bufferViews'].append({
                    'buffer' : 0,
                    'byteOffset': len(bin_data),
                    'byteLength': len(inv_mtx_buffer) # or 16 * 4 * (i + 1)
                })
                bin_data += inv_mtx_buffer
                buffer_view += 1

    gltf_data['scenes'][0]['nodes'].extend(x for x in range(bc, len(gltf_data['nodes'])))
    gltf_data['buffers'].append({
        'byteLength': len(bin_data),
        'uri': f'{output_file.stem}.bin'
    })
    # https://gitlab.com/dodgyville/pygltflib
    # https://github.com/eArmada8/ed8pkg2gltf/blob/main/extract_from_gltf.py
    # https://github.com/KhronosGroup/glTF/blob/main/extensions/1.0/Khronos/KHR_binary_glTF/README.md
    bin_file = output_file.parent / f'{output_file.stem}.bin'
    bin_file.write_bytes(bin_data)
    with output_file.open('w', encoding='UTF-8') as g:
        json.dump(gltf_data, g, indent=4)

def extractG1M(data: bytes, pos: int, output_file: Path):
    """
    Parse G1M data (bytes) and write it to output_file (glTF only at this time)
    If skeleton is external, doesn't write files, but adds to scene, to be processed later
    """
    g1mHeader = G1MHeader(*unpack_from(E+III_STRUCT, data, 12))
    pos += g1mHeader.firstChunkOffset
    for _ in range(g1mHeader.chunkCount):
        header = GResourceHeader(*unpack_from(E+'4s2I', data, pos)) # do nothing with version
        magic = GUST_MAGICS[header.magic] if E == '<' else header.magic.decode()
        if magic == 'G1MG':
            G1MGs.append(G1MG(data, pos))
        if magic == 'G1MM':
            # WIP: G1MMs.append(G1MM(data, pos)) # WIP: No code to rely on
            pass
        elif magic == 'G1MS' and not SKELETON_INTERNAL_INDEXP1:
            # WIP: If there are multiple skeletons, they seem to be different poses (bHasParsedG1MS if use them all?)
            skel = G1MS(data, pos, header.chunkVersion)
            if skel.bIsInternal:
                SKELETON_INTERNAL_INDEXP1 = len(G1MSs) + 1
                """
                # WIP: Backup. See also G1MS_Process
                for i, bone in enumerate(skel.joints):
                    if bone.parentID != 0xFFFFFFFF and bone.parentID < len(skel.joints):
                        parent_bone = skel.joints[bone.parentID] # ProjectG1M says skel.getJoint(bone.parentID)
                        skel.joints[i].abs_tm = calc_abs_rotation_position(bone, parent_bone)
                """
            G1MSs.append(skel)
        elif TRANSFORM_CLOTH_MESH: # WIP: I think this option means something else?
            if magic == 'NUNO':
                NUNOs.append(NUNO(data, pos))
            elif magic == 'NUNV':
                NUNVs.append(NUNV(data, pos))
            elif magic == 'NUNS':
                NUNSs.append(NUNS(data, pos))
            elif magic == 'SOFT':
                # WIP: SOFTs.append(SOFT(data[pos:pos + header.chunkSize])) # WIP: append or process?
                pass
            # WIP: eArmada8's script only carries max. one for each nun type
        # Skipping other sections, like EXTR
        pos += header.chunkSize
    # IS_G1MS_UNORDERED = header.chunkVersion < 0x30303332
    if SKELETON_INTERNAL_INDEXP1: write_glTF(G1MSs[SKELETON_INTERNAL_INDEXP1 - 1], G1MGs[0], data, output_file, True)
    # https://stackoverflow.com/questions/71266731/how-to-convert-nested-classes-to-json-or-dict
    # if isinstance(obj, Quaternion): return obj.rotation_matrix.tolist()
    # not dumping skeleton as .json at this time, as modifying the skeleton is not supported (currently)

def extractG1T(input_file: Path):
    backup(input_file.parent / input_file.stem)
    subprocess.call([g1t_extract, str(input_file)])

# WIP possibly put this into the gust lib, together with the formats
def setEndianMagic(magic: bytes):
    """
    Set the endian, depending on the magic.
    Returns file extension according to magic, if the endian was set, otherwise None if magic wasn't found.
    """
    global E
    e = getFileExtension(magic)
    if e != '.bin':
        E = '<'
        return e
    e = getFileExtension(magic, True)
    if e != '.bin':
        E = '>'
        return e
    return None

def setEndianFile(input_file: Path):
    with input_file.open('rb') as f: return setEndianMagic(f.read(4))

def extractG1(data: bytes, output_file: Path, pos: int = 0):
    backup(output_file)
    # WIP: Here comes the moment, where either all files are extracted (for g1m merge), or a Blender handling/dialogue is used
    match output_file.suffix:
        case '.g1m':
            extractG1M(data, pos, output_file)
        case '.g1t':
            pass # WIP
        case '.g1a':
            output_file.write_bytes(data) # WIP
        case '.g2a':
            output_file.write_bytes(data) # WIP
        case _:
            # add more...
            output_file.write_bytes(data)

def extractG(data: bytes, offsets: tuple, output_folder: Path):
    for i, pos in offsets:
        e = setEndianMagic(data[pos:pos + 12].split(b'\x00')[0])
        if e: extractG1(data, output_folder / (str(i).zfill(4) + e), pos)

def _extractG(input_file: Path, output_folder: Path):
    e = setEndianFile(input_file)
    if not e or input_file.stat().st_size < 12: return
    # WIP: Here comes the moment, where either all files are extracted (for g1m merge), or a Blender handling/dialogue is used
    if e == '.g1t':
        extractG1T(input_file) # temporary
    else:
        extractG1(input_file.read_bytes(), output_folder / (input_file.stem + e))

def _tryextractG1M(input_files: list, input_folder: Path):
    for f in input_files:
        f = input_folder / input_files # files should be without path, but I'm not sure
        if f.exists():
            _extractG(f, f.parent / f.stem)

def _extractZ(input_file: Path, output_folder: Path):
    if output_folder.suffix.casefold() == '.bin':
        data = un_pack(input_file)
        extractG(data, get_offsets(data), output_folder)
    else:
        extractG(un_pack(input_file), (0), output_folder)

def _extractB(input_file: Path, output_folder: Path):
    data = input_file.read_bytes()
    extractG(data, get_offsets(data), output_folder)

def _combine(input_folder: Path, output_file: Path):
    backup(output_file)
    output_file.write_bytes(combine(input_folder))

def main():
    parser = ArgumentParser()
    parser.add_argument('input', help='input file (supports glob)')
    parser.add_argument('-k', '--keep_color', help="Preserve vertex color attribute", action="store_true")
    args = parser.parse_args()
    input_files = glob.glob(args.input.replace('[', '[[]'), recursive=True)
    """ Option possibilities:
    path to texture file
    "Select G1T when non/partial merge" "Select the G1T file manually."
    "Merge all assets in the same folder" "Merges all the g1m, g1t, oid and g1a/g2a files."
    "Only models when merging" "If the merging option is set, only merge the g1m files and ignore the others."
    "Additive animations" "Set to true if the animations are additive."
    "Process vertex colors" "Extract the vertex colors."
    "Display physics drivers" "Display the physics drivers."
    "Disable physics nodes" "Only keep the base skeleton, ignoring the physics nodes."
    "No first texture rename" "Do not rename the first texture to 0.dds."
    "Enable NUN autorig" "Autorig NUN meshes."
    "Load all LODs for meshes" "Load all LODs"
    bTRANSLATE_MESHES: Move model to root node (skeleton?)
    """

    if not input_files:
        raise ValueError('No files found')

    for oid in (o for o in input_files if o[-4:].casefold() == '.oid' or o[-7:].casefold() == 'Oid.bin'):
        # get bone ids first
        OID(Path(oid).read_bytes)

    for input_file in input_files:
        input_file = Path(input_file)
        ext = input_file.suffix.casefold()
        output_folder = input_file.parent / input_file.stem
        output_folder.mkdir(parents=True, exist_ok=True)

        if input_file.is_dir():
            # WIP: Might change to use extraction on all files instead
            output_file = Path(f'{input_file}{'.ZL_' if ext else '.bin.ZL_'}')
            _combine(input_file, output_file)
        elif input_file.suffix.upper() == '.ZL_':
            _extractZ(input_file, output_folder)
        elif ext == '.bin':
            _extractB(input_file, output_folder)
        elif ext in (['.g1m', '.g1t', '.g1a', '.g2a'] if bMERGE else ['.g1m']):
            # WIP: Improve merge logic in _extractG1. Texture order/name is important.
            _extractG(input_file, output_folder)
            # from g1m_export_meshes import parseG1M
            #parseG1M(f'{input_file.parent / input_file.stem}', overwrite=False, write_buffers=True, cull_vertices=False, transform_cloth=True, write_empty_buffers=False)
        elif ext in ['.g2a', '.g1a']:
            # _extractG(input_file, output_folder)
            pass # WIP
        elif ext == '.g1t': # Texture
            _extractG(input_file, output_folder)
        # Any other file formats? MUA3 doesn't seem to have OBJD (extension?), and lmpk don't seem to belong into this category
        # WIP: json files seem to contain numbers in hex format that might have to be converted to int(x, 16)
        elif input_file.name == 'elixir.json':
            with input_file.open(encoding='UTF-8') as f:
                elixir = json.load(f)
            _tryextractG1M([x for x in elixir['files'] if x[-4:] == '.g1m'], input_file.parent)
        elif input_file.name == 'gmpk.json':
            with input_file.open(encoding='UTF-8') as f:
                gmpk = json.load(f)
            _tryextractG1M([f'{x['name']}.g1m' for x in gmpk['SDP']['NID']['names']], input_file.parent)
        else: # check if Gust file
            _extractG(input_file, output_folder)

if __name__ == '__main__':
    main()