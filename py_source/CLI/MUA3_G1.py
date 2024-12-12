# Koei Tecmo's Gust files extractor and combiner for MUA3
# by eArmada8, Joschuka and three-houses-research-team, yretenai (creator of Cethleann), ..., ak2yny
# WIP: using byte stream instead of bytes could speed up the process: io.BytesIO(data) as f (f.read(4)), but bytearray should be the fastest

# native
import json, glob
from argparse import ArgumentParser
from pathlib import Path
from struct import pack, calcsize, unpack_from

# requirements
import numpy as np
from pyquaternion import Quaternion

# project
from .MUA3_Formats import GUST_MAGICS
from .MUA3_BIN import combine, get_offsets
from .MUA3_G1_Helper import extractG1T, setEndianFile, setEndianMagic
from .MUA3_ZL import backup, un_pack

# from Blender.g1m_export_meshes import parseG1M
from .lib.lib_gust import *
from .lib.lib_g1m import calc_abs_rotation_position, compute_center_of_mass, G1MHeader, G1MG, G1MG_HEADER_STRUCT, G1MGVAStructType, G1MS, make_nun_bones # *, G1MM
from .lib.lib_g1t import dds_to_g1t_json, g1t_to_dds
# from .lib.lib_g2a import G1A, G2A # WIP
from .lib.lib_nun import NUNO, NUNV, NUNS
from .lib.lib_oid import GLOBAL2OID, OID


# Import settings
bENABLE_NUNNODES = bTRANSLATE_MESHES = True

bMERGE = bLOADALLLODS = False

SKELETON_INTERNAL_INDEXP1 = 0
# WIP: Might need a common dict with ID, so to preserve the file order
G1MGs, G1MMs, G1MSs, NUNOs, NUNVs, NUNSs, SOFTs = ([] for _ in range(7))
# SKELETON_LAYER = 1 # Custom layering system from Noesis plugin

STRUCT_TO_GLTF_TYPE = {
    'B': ('SCALAR', 5121),
    'H': ('SCALAR', 5123),
    'I': ('SCALAR', 5125),
    'L': ('SCALAR', 5125),
    'f': ('SCALAR', 5126),
    '2f': ('VEC2', 5126),
    '3f': ('VEC3', 5126),
    '4f': ('VEC4', 5126),
    '4B': ('VEC4', 5121),
    '4H': ('VEC4', 5123),
    '4I': ('VEC4', 5125)
    # '2e': (), # half floats are not supported
    # '4e': (),
    # 'BBBB', # unorm are not supported
    # 'Q': (),
}

"""
# these classes follow the fmt vb, ib companion, but the G1MG class should hold all the information needed
@dataclass
class DriverMeshEntry:
    ID: int
    SemanticName: str
    SemanticIndex: int = 0
    Format: str = 'R32G32B32_FLOAT'
    InputSlot: int = 0
    AlignedByteOffset: int = 0
    InputSlotClass: str = 'per-vertex'
    InstanceDataStepRate: int = 0

# WIP: should it be dataclass to fix __dict__?
class DriverMesh:
    stride: int = 36
    topology: str = 'trianglelist'
    Format: str = 'DXGI_FORMAT_R16_UINT'
    elements: list = [DriverMeshEntry(0, 'POSITION'),
                      DriverMeshEntry(1, 'WEIGHTS', Format = 'R32G32B32A32_FLOAT', AlignedByteOffset = 12),
                      DriverMeshEntry(2, 'JOINTS', Format = 'R16G16B16A16_UINT', AlignedByteOffset = 28),]

Unused
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


def extractTexture(data: str, noeTex: list):
    G1T(data, noeTex) # WIP: not implemented
    # WIP: rename texture

WIP: Layering external skeletons (but could probably be simplified a lot) or use combine_skeleton
     No need for jointLocalIndexToExtract, as building the skeleton can check for existing bones on the fly.
     should it be globalIndices.append(k + (SKELETON_LAYER if skel.bIsInternal else 0) * 1000) ?
     ^^ could even use this instead of globalIndexToLayers, probably
def G1MS_Process(s: G1MS, jointIndex: int):
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

        
WIP: G1M2glTF notes:
- 
"""

def write_glTF(s: G1MS, g1mg: G1MG, data: bytes, output_file: Path, keep_color: bool):
    # Could support multiple scenes in the future
    # Currently doesn't support culling (ib not modified) (see cull_vb)
    # WIP: Some buffers are not compatible: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#mesheshttps://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#meshes
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
            gltf_data['images'] = [{'uri': f'{i:03d}.dds'} for i in range(max(x.index for y in g1mg.materials for x in y.g1mgTextures) + 1)]
        for i, mat in enumerate(g1mg.materials):
            material = {'name': f'Material_{i:02d}'}
            for j, tex in enumerate(mat.g1mgTextures):
                gltf_t = {'index' : idx, 'texCoord': tex.layer} # WIP: UV didn't work, so tex.layer is probably wrong (might have to be the TEXCOORD buffer index)
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

    # WIP: Could use multiple skeletons and layers?
    # WIP: Could add nun skeleton after merge
    # Note: This raises an exception, if parent hasn't been updated before the child
    for i, bone in enumerate(s.joints):
        # WIP: Can't have NUN bones? There's no reason for it to fail, so i is used instead of len(gltf_data['nodes'])
        if bone.parentID != 0xFFFFFFFF and bone.parentID < len(s.joints):
            s.joints[i].abs_tm = calc_abs_rotation_position(bone, s.joints[bone.parentID])
        node = {'children': [], 'name': s.getName(i, GLOBAL2OID)}
        if bone.rotation != (1, 0, 0, 0): node['rotation'] = (bone.rx, bone.ry, bone.rz, bone.rw)
        if bone.scale != (1, 1, 1): node['scale'] = bone.scale
        if bone.position != (0, 0, 0): node['translation'] = bone.position
        if i > 0: gltf_data['nodes'][bone.parentID]['children'].append(i)
        gltf_data['nodes'].append(node)
    bc = i + 1
    for i in range(bc):
        if not gltf_data['nodes'][i]['children']: del(gltf_data['nodes'][i]['children'])
    # temp: duplicate nun stuff

    for subindex, submesh in enumerate(g1mg.submeshes):
        # WIP: Some submeshes seem to refer to the same buffer, but the buffer is added multiple times
        #      if vbi != submesh.vertexBufferIndex:
        # if ib.count > 0:
        #   gltf_data['scenes'][0]['nodes'].append(bc)
        #   bc += 1, rename to nc
        vbi = submesh.vertexBufferIndex
        submesh_lod = next(x for y in g1mg.meshGroups for x in y.meshes if subindex in x.indices)
        print(f'Processing submesh {subindex} type {submesh_lod.meshType}...')
        # Note: Some say that all buffers should be capped to first vb.count (zip would do the same, but I don't know if zip is useful)
        buf = {
            'POSITION': list(g1mg.get_vb(vbi, 'POSITION', data)),
            'JOINTS': list(g1mg.get_vb(vbi, 'JOINTS', data)), # [tuple(j // 3 for j in i) for i in g1mg.get_vb(vbi, 'JOINTS', data)], # something to do with triangles?,
            'WEIGHTS': list(g1mg.get_vb(vbi, 'WEIGHTS', data)),
            'TANGENT': list(g1mg.get_vb(vbi, 'TANGENT', data))
        }
        nun = None
        # WIP:
        # look in write_submeshes
        # submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata, model_skel_data, fmts, e=e, cull_vertices = True, preserve_trianglestrip = True)
        if submesh_lod.meshType == 1: # and not bDISABLENUNNODES | NUNO or NUNV
            NUNID = submesh_lod.externalID % 10000
            # WIP: This should be the a nun from the same file. Need make sure of that.
            # ProjectG1M uses fileID and map. It's difficult to grasp, but I think the externalID adds up to be the respective index in the list (of the type in the same file)
            if -1 < submesh_lod.externalID and submesh_lod.externalID < 10000:
                for n in NUNOs:
                    if NUNID < len(n.Nuno1): nun = n.Nuno1[NUNID]
            elif submesh_lod.externalID < 20000:
                for n in NUNVs:
                    if NUNID < len(n.Nunv1): nun = n.Nunv1[NUNID]
            elif submesh_lod.externalID < 30000:
                # NUNO5s are different, but share the layer. Might need to update logic, though.
                for n in NUNOs:
                    if NUNID < len(n.Nuno3n5): nun = n.Nuno3n5[NUNID]
            if nun: # try
                # WIP: I could possibly do the calculations externally and return the buffer.
                # Since nun skeleton is per NUN (NUNO1, etc.) it shouldn't be better to build the nun skeleton in advance
                name_prefix = f'physbone_{type(nun).__name__}'
                parent_joint = s.getJoint(nun.parentBoneID)
                nun_bones = make_nun_bones(nun, s) # WIP: should append NUN bones to skeleton, but how, so that the indices match?
                buf['NORMAL'] = list(g1mg.get_vb(vbi, 'NORMAL', data))
                buf['BINORMAL'] = list(g1mg.get_vb(vbi, 'BINORMAL', data))
                buf['FOG'] = list(g1mg.get_vb(vbi, 'FOG', data))
                buf['PSIZE'] = list(g1mg.get_vb(vbi, 'PSIZE', data)) # cloth_stuff_1_b
                cloth_stuff_2_b = list(g1mg.get_vb(vbi, 'TEXCOORD', data, layer_threshold=2)) # Not really sure
                # cloth_stuff_3_b = [x[3] for x in g1mg.get_vb(vbi, 'POSITION', data)]
                cloth_stuff_4_b = [x[3] for x in g1mg.get_vb(vbi, 'NORMAL', data)]
                cloth_stuff_5_b = list(g1mg.get_vb(vbi, 'COLOR', data, layer_threshold=0))
                vertPosBuff = []
                vertNormBuff = []
                tangentBuffer = []
                for i, clothPosition in enumerate(buf['POSITION']):
                    if buf['BINORMAL'][i] == (0,0,0,0):
                        vertPosBuff.append(tuple(Quaternion(matrix=parent_joint.abs_tm).rotate(clothPosition[:3]) + parent_joint.abs_tm[3,:3]))
                        vertNormBuff.append(buf['NORMAL'][i])
                        if buf['TANGENT']: tangentBuffer.append(buf['TANGENT'][i])
                    else:
                        a = (0, 0, 0)
                        a += compute_center_of_mass((0, 0, 0), clothPosition, buf['JOINTS'][i], nun_bones) * buf['WEIGHTS'][i][0]
                        a += compute_center_of_mass((0, 0, 0), clothPosition, buf['PSIZE'][i], nun_bones) * buf['WEIGHTS'][i][1]
                        a += compute_center_of_mass((0, 0, 0), clothPosition, buf['FOG'][i], nun_bones) * buf['WEIGHTS'][i][2]
                        a += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_2_b[i], nun_bones) * buf['WEIGHTS'][i][3]
                        b = (0, 0, 0)
                        b += compute_center_of_mass((0, 0, 0), clothPosition, buf['JOINTS'][i], nun_bones) * cloth_stuff_5_b[i][0]
                        b += compute_center_of_mass((0, 0, 0), clothPosition, buf['PSIZE'][i], nun_bones) * cloth_stuff_5_b[i][1]
                        b += compute_center_of_mass((0, 0, 0), clothPosition, buf['FOG'][i], nun_bones) * cloth_stuff_5_b[i][2]
                        b += compute_center_of_mass((0, 0, 0), clothPosition, cloth_stuff_2_b[i], nun_bones) * cloth_stuff_5_b[i][3]
                        c = (0, 0, 0)
                        c += compute_center_of_mass((0, 0, 0), buf['BINORMAL'][i], buf['JOINTS'][i], nun_bones) * buf['WEIGHTS'][i][0]
                        c += compute_center_of_mass((0, 0, 0), buf['BINORMAL'][i], buf['PSIZE'][i], nun_bones) * buf['WEIGHTS'][i][1]
                        c += compute_center_of_mass((0, 0, 0), buf['BINORMAL'][i], buf['FOG'][i], nun_bones) * buf['WEIGHTS'][i][2]
                        c += compute_center_of_mass((0, 0, 0), buf['BINORMAL'][i], cloth_stuff_2_b[i], nun_bones) * buf['WEIGHTS'][i][3]
                        d = np.cross(b, c)
                        vertPosBuff.append(tuple((d / np.linalg.norm(d) if name_prefix[-1] == '5' else d) * cloth_stuff_4_b[i] + a)) # WIP: What are other differences with NUNO5?
                        e = b * buf['NORMAL'][i][1] + c * buf['NORMAL'][i][0] + d * buf['NORMAL'][i][2]
                        vertNormBuff.append(tuple(e / np.linalg.norm(e)))
                        if buf['TANGENT']:
                            e = b * buf['TANGENT'][i][1] + c * buf['TANGENT'][i][0] + d * buf['TANGENT'][i][2]
                            tangentBuffer.append(tuple(e / np.linalg.norm(e)) + (buf['TANGENT'][i][3],))
                buf['POSITION'] = vertPosBuff
                buf['NORMAL'] = vertNormBuff
                buf['sPOSITION'] = buf['sNORMAL'] = '3f'
                if buf['TANGENT']:
                    buf['TANGENT'] = tangentBuffer
                    buf['sTANGENT'] = '4f'
        elif submesh_lod.meshType == 2:
            # Is this SOFT?
            palette = g1mg.joint_palettes[submesh.bonePaletteIndex]
            physicsBoneList = [x.physicsIndex & 0xFFFF if x.physicsIndex >> 31 else x.physicsIndex for x in palette.joints]
            phys_bone_count = len(palette.joints)
            oldSkinIndiceList = buf['JOINTS'] if buf['JOINTS'] else [(0, 0, 0, 0)] * len(buf['POSITION'])
            vertPosBuff = []
            for i, physPos in enumerate(buf['POSITION']):
                index = oldSkinIndiceList[i][0] // 3 # 2 extras each (physics?)
                if index < phys_bone_count and physicsBoneList[index] < s.header.jointCount:
                    tm = s.joints[physicsBoneList[index]].abs_tm
                    q1 = Quaternion(matrix=tm)
                    q2 = Quaternion([q1[0], 0 - q1[1], 0 - q1[2], 0 - q1[3]]) \
                        * Quaternion(0, physPos[0], physPos[1], physPos[2]) * q1
                    vertPosBuff.append(tuple(tm[3,:3] + (q2[1], q2[2], q2[3])))
            buf['POSITION'] = vertPosBuff
            buf['sPOSITION'] = '3f'
        else:
            # Only process 3D submeshes
            # WIP: could one use [x[:3] for x in buf['POSITION']] ?
            if next(x.dataType for x in g1mg.vertexAttributeSets[vbi].attributes if x.semantic == 'POSITION') != 2:
                continue

        # if len(ib) > 0
        if buf['WEIGHTS']:
            d = len(buf['JOINTS'][0]) - len(buf['WEIGHTS'][0]) # if there aren't enough weight values, they should be expanded | WIP: Numpy could be helpful once again
            if d > 0:
                buf['sWEIGHTS'] = f'{len(buf['JOINTS'][0])}f' # prefices = ['R','G','B','A','D']
                for _ in range(d):
                    for i, sw in enumerate(buf['WEIGHTS']):
                        w = 1 - sum(sw)
                        buf['WEIGHTS'][i] = sw + (0 if w < 0.00001 else w,)
        # WIP: Remove cloth weights: for i, sw in enumerate(buf['WEIGHTS']): (if sw[0] != max(sw), probably): buf['WEIGHTS'][i] = (1,) + sw[1:] and buf['WEIGHTS'][i] = tuple(0 for _ in range(len(sw)))
        #      But why would I add cloth weights to begin with?
        if submesh_lod.meshType != 0: # cloth
            for i, t in enumerate(buf['TANGENT']):
                buf['TANGENT'][i] = tuple(t[:3] / np.linalg.norm(t[:3])) + t[3:]
        # Move model to root node if bTRANSLATE_MESHES set to True
        if bTRANSLATE_MESHES and 'translation' in gltf_data['nodes'][0]:
            position_veclength = len(buf['POSITION'][0]) # should be at least 3
            shift = np.array(gltf_data['nodes'][0]['translation'] + (0,) * (position_veclength - 3))
            buf['POSITION'] = [tuple(p[:3] + shift) for p in buf['POSITION']]
            # buf['sPOSITION'] = '3f' limit to 3D? would be done before.
        primitive = {"attributes":{}}
        block_offset = len(bin_data)
        for i, a in enumerate(g1mg.vertexAttributeSets[vbi].attributes): # is the order correct?
            # WIP: if remove_physics and a.semantic not in ['POSITION', 'WEIGHTS', 'JOINTS', 'NORMAL', 'COLOR', 'TEXCOORD', 'TANGENT']: continue
            if a.semantic == 'COLOR' and not keep_color: continue # or remove from primitive["attributes"] afterwards
            vbe = g1mg.vertex_buffers[g1mg.vertexAttributeSets[vbi].vBufferIndices[a.bufferID]]
            vb = buf[a.semantic] if a.layer == 0 and a.semantic in buf else \
                list(unpack_from(f'{E} {G1MGVAStructType[a.dataType]}', data, p) for p in range(vbe.offset + a.offset, vbe.offset + a.offset + vbe.count * vbe.stride, vbe.stride)) # duplicate code, in case there are problems
            if not vb: continue
            # NORMAL must be VEC3. This and a few other buffers need to be checked and modified or reported
            if a.layer == 0 and (v := buf.get(f's{a.semantic}')):
                a.dataType = v
                vbe.count = len(vb) # possibly use on all attribues (see below)
            else:
                a.dataType = G1MGVAStructType[a.dataType]
            if a.dataType not in STRUCT_TO_GLTF_TYPE: a.dataType = f'{a.dataType[0]}f' if a.dataType[0].isdigit() else f'{len(a.dataType)}f'
            gltf_type = STRUCT_TO_GLTF_TYPE[a.dataType]
            sem = f'{a.semantic}_{i}' if a.semantic in ('WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD') else a.semantic
            byte_length = vbe.count * calcsize(a.dataType)
            primitive["attributes"][sem] = len(gltf_data['accessors'])
            gltf_data['accessors'].append({
                'bufferView' : buffer_view,
                'componentType': gltf_type[1],
                'count': vbe.count, # possibly len(vb)
                'type': gltf_type[0]
            })
            if a.semantic == 'POSITION':
                gltf_data['accessors'][-1]['max'] = tuple(max(v) for v in zip(*vb))
                gltf_data['accessors'][-1]['min'] = tuple(min(v) for v in zip(*vb))
            gltf_data['bufferViews'].append({
                'buffer' : 0,
                'byteOffset': block_offset,
                'byteLength': byte_length
            })
            # Endian? | Could there be a straight buffer copy without struct?, But can't convert unsupported formats, then
            bin_data += pack(f'{E} {a.dataType * vbe.count}', *sum(vb, ())) # WIP: Must all be tuples | alt. use numpy (np.vstack(np.fromiter(generator, tuple))) and unpack like this: *vb.ravel()
            block_offset += byte_length
            buffer_view += 1
        ib = g1mg.index_buffers[submesh.indexBufferIndex]
        # if ib.npDataType.char not in STRUCT_TO_GLTF_TYPE: ib.dataType = 'I' # This will only work when unpacked
        if ib.dataType > 32: raise ValueError('64bit data type not supported.')
        primitive["indices"] = len(gltf_data['accessors'])
        gltf_data['accessors'].append({
            'bufferView' : buffer_view,
            'componentType': ib.glTF_acc,
            'count': ib.count,
            'type': ib.glTF_typ
        })
        # WIP: ??
        if a.semantic == 'POSITION':
            gltf_data['accessors'][-1]['max'] = tuple(max(v) for v in zip(*buf['POSITION']))
            gltf_data['accessors'][-1]['min'] = tuple(min(v) for v in zip(*buf['POSITION']))
        gltf_data['bufferViews'].append({
            'buffer' : 0,
            'byteOffset': block_offset,
            'byteLength': ib.count * ib.bitwidth,
            'target': 34963
        })
        bin_data += data[ib.offset:ib.offset + ib.count * ib.bitwidth]
        buffer_view += 1
        # ib = unpack_from(f'{E} {ib.count}{ib.npDataType.char}', data, ib.offset)

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

        if s.bIsInternal and s.header.jointCount > 1 and buf['WEIGHTS'] and submesh_lod.meshType == 2:
            gltf_data['nodes'][-1]['skin'] = len(gltf_data['skins'])
            inv_mtx_buffer = bytes()
            skin_bones = []
            for i, j in enumerate(palette.joints):
                skin_bones.append(j.jointIndex) # WIP: Is this global or local? I need global (i.e. the bone's index)
                mtx = s.getJoint(j.jointIndex).abs_tm # WIP: Is this global or local?
                inv_mtx_buffer += pack(E+'16f', *np.ndarray.transpose(np.linalg.inv(mtx)).flatten())
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
    output_file.with_suffix('.bin').write_bytes(bin_data)
    with output_file.with_suffix('.gltf').open('w', encoding='UTF-8') as g:
        json.dump(gltf_data, g, indent=4)

def extractG1M(data: bytes, pos: int, output_file: Path):
    """
    Parse G1M data (bytes) and write it to output_file (glTF only at this time)
    If skeleton is external, doesn't write files, but adds to scene, to be processed later
    """
    g1mHeader = G1MHeader(*unpack_from(E+III_STRUCT, data, pos + 12))
    pos += g1mHeader.firstChunkOffset
    global SKELETON_INTERNAL_INDEXP1
    for _ in range(g1mHeader.chunkCount):
        header = GResourceHeader(*unpack_from(E+'4s2I', data, pos)) # do nothing with version
        magic = GUST_MAGICS[header.magic] if E == '<' else header.magic.decode()
        if magic == 'G1MG':
            G1MGs.append(G1MG(*unpack_from(f'{E} 4s2I{G1MG_HEADER_STRUCT}', data, pos), data, pos))
        elif magic == 'G1MM':
            # WIP: G1MMs.append(G1MM(data, pos)) # WIP: No code to rely on
            pass
        elif magic == 'G1MS' and not SKELETON_INTERNAL_INDEXP1:
            # WIP: If there are multiple skeletons, they seem to be different poses (bHasParsedG1MS if use them all?)
            skel = G1MS(data, pos, header.chunkVersion)
            G1MSs.append(skel)
            if skel.bIsInternal:
                SKELETON_INTERNAL_INDEXP1 = len(G1MSs)
                """
                # WIP: Backup. See also G1MS_Process
                for i, bone in enumerate(skel.joints):
                    if bone.parentID != 0xFFFFFFFF and bone.parentID < len(skel.joints):
                        parent_bone = skel.joints[bone.parentID] # ProjectG1M says skel.getJoint(bone.parentID)
                        skel.joints[i].abs_tm = calc_abs_rotation_position(bone, parent_bone)
                """
        elif bENABLE_NUNNODES:
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
    # WIP: Doesn't account for scenes withou skeletons or multiple G1MGs or multiple/different files
    if SKELETON_INTERNAL_INDEXP1: write_glTF(G1MSs[SKELETON_INTERNAL_INDEXP1 - 1], G1MGs[-1], data, output_file, True)
    # https://stackoverflow.com/questions/71266731/how-to-convert-nested-classes-to-json-or-dict
    # if isinstance(obj, Quaternion): return obj.rotation_matrix.tolist()
    # not dumping skeleton as .json at this time, as modifying the skeleton is not supported (currently)

def _extractG1(data: bytes, output_file: Path, pos: int = 0, next_pos: int = 0):
    backup(output_file)
    # WIP: Here comes the moment, where either all files are extracted (for g1m merge), or a Blender handling/dialogue is used
    match output_file.suffix:
        case '.g1m':
            extractG1M(data, pos, output_file)
        case '.g1t':
            g1t_to_dds(data, output_file.parent, False)
        case '.g1a':
            output_file.write_bytes(data[pos:next_pos]) # WIP
        case '.g2a':
            output_file.write_bytes(data[pos:next_pos]) # WIP
        case _:
            # add more...
            output_file.write_bytes(data[pos:next_pos])

def extractG(data: bytes, offsets: tuple, output_folder: Path):
    for i, pos in enumerate(offsets):
        e = setEndianMagic(data[pos:pos + 12].split(b'\x00')[0])
        if e: _extractG1(data, output_folder / f'{i:04d}{e}', pos, offsets[i + 1] if i + 1 < len(offsets) else len(data))

    # temporary fallback (not for anims at this time) - would need individual file IDs to match skeletons and G1MGs:
    if e == '.g1m' and not SKELETON_INTERNAL_INDEXP1:
        write_glTF(G1MSs[0], G1MGs[0], data, output_folder / '0000' + e)

def _extractG(input_file: Path, output_folder: Path):
    e = setEndianFile(input_file)
    sz = input_file.stat().st_size
    if not e or sz < 12: return
    # WIP: Here comes the moment, where either all files are extracted (for g1m merge), or a Blender handling/dialogue is used
    if e == '.g1t':
        extractG1T(input_file)
    else:
        _extractG1(input_file.read_bytes(), output_folder / (input_file.stem + e), sz)

def _tryextractG1M(input_files: list, input_folder: Path):
    for f in input_files:
        f = input_folder / f # files should be without path, but I'm not sure
        if f.exists():
            _extractG(f, f.with_suffix(''))

def _extractZ(input_file: Path, output_folder: Path):
    if output_folder.suffix.casefold() == '.bin':
        data = un_pack(input_file)
        extractG(data, get_offsets(data), output_folder)
    else:
        extractG(un_pack(input_file), (0,), output_folder.with_suffix(''))

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
    bG1TMERGEG1MONLY "Select G1T when non/partial merge" "Select the G1T file manually."
    bMERGE "Merge all assets in the same folder" "Merges all the g1m, g1t, oid and g1a/g2a files."
    bMERGEG1MONLY "Only models when merging" "If the merging option is set, only merge the g1m files and ignore the others."
    bADDITIVE "Additive animations" "Set to true if the animations are additive."
    bCOLOR "Process vertex colors" "Extract the vertex colors."
    bDISPLAYDRIVER "Display physics drivers" "Display the physics drivers."
    bDISABLENUNNODES "Disable physics nodes" "Only keep the base skeleton, ignoring the physics nodes."
    bNOTEXTURERENAME "No first texture rename" "Do not rename the first texture to 0.dds."
    bENABLENUNAUTORIG "Enable NUN autorig" "Autorig NUN meshes."
    bLOADALLLODS "Load all LODs for meshes" "Load all LODs"
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
        output_folder = input_file.with_suffix('')
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
            #parseG1M(f'{input_file.with_suffix('')}', overwrite=False, write_buffers=True, cull_vertices=False, transform_cloth=True, write_empty_buffers=False)
        elif ext in ['.g2a', '.g1a']:
            # _extractG(input_file, output_folder)
            pass # WIP
        elif ext == '.g1t': # Texture
            _extractG(input_file, output_folder)
        elif input_file.name == 'g1t.json':
            with input_file.open('r') as f:
                json_data = json.load(f)
            dds_to_g1t_json(input_file.parent, json_data, False)
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