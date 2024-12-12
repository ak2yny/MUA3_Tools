# Based primarily off of:
#   - https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
#   - https://github.com/eArmada8/gust_stuff
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html

# bl_info = {
#     "name": "MUA3 Gust Importer, Exporter",
#     "author": "DarkstarSword, eArmada8, Joschuka, ak2yny",
#     "version": (0, 0, 3),
#     "blender": (4, 10, 0), # depends, need modern Python, etc.
#     "location": "File > Import-Export",
#     "category": "Import",
# }


from enum import Enum
from pathlib import Path
from struct import unpack_from

# Project
from .lib.lib_g1m import G1MGVertexAttribute, G1MHeader, G1MG, G1MG_HEADER_STRUCT, G1MGVAFormat # *, G1MM, G1MS, make_nun_bones, calc_abs_rotation_position, compute_center_of_mass
from .lib.lib_g1t import g1t_to_dds
from .lib.lib_gust import *
from .lib.lib_nun import NUNO, NUNV, NUNS
from .MUA3_BIN import get_offsets
from .MUA3_Formats import GUST_MAGICS
from .MUA3_G1_Helper import setEndianMagic
from .MUA3_ZL import un_pack

# Blender
import bpy
from bpy_extras.io_utils import axis_conversion, ImportHelper # , orientation_helper
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, StringProperty # , IntProperty
import numpy as np


# Settings:
SUPPORTED_TOPOLOGIES = ('trianglelist', 'pointlist', 'trianglestrip') # WIP: pointlist?

G1MGs, G1MMs, G1MSs, NUNOs, NUNVs, NUNSs, SOFTs = ([] for _ in range(7))
SKELETON_INTERNAL_INDEXP1 = 0
MESHES_ADDED = []


# =================================================================
# Blender import class with options
# =================================================================

# scene = bpy.context.scene

class DialogueError(Exception): pass

# @orientation_helper(axis_forward='-Z', axis_up='Y')
class MUA3_Gust_Import(bpy.types.Operator, ImportHelper):
    """Import .g1m 3D objects and associated files from Marvel Ultimate Alliance 3 and other compatible games."""
                                                 # ^^ Use this as a tooltip.
    bl_idname = 'mua3.gust_import'               # Unique identifier.
    bl_label = 'Import Gust Files from MUA3'     # Display name in the interface.
    bl_options = {'PRESET', 'REGISTER', 'UNDO'}  # Enable undo for the operator. WIP: Remove register?

    # For ImportHelper
    filename_ext = '.ZL_' # or .bin, .g1m
    filter_glob: StringProperty(
            default='*.ZL_;*.bin;*.g1m;*.g1a;*.g2a',
            options={'HIDDEN'},
    )

    files: CollectionProperty(
            name='File Path',
            type=bpy.types.OperatorFileListElement,
    )

    # Options
    all_lod: BoolProperty(
            name = 'Import All LOD',
            description = 'Import the mesh for each LOD.',
            default = False,
    )

    lod: EnumProperty(
            name = 'Select LOD',
            description = 'Select which LOD to import.',
            items = (
                     ('0', 'LOD0', 'Highest level of detail'),
                     ('1', 'LOD1', ''),
                     ('2', 'LOD2', ''),
                     ('3', 'LOD3', ''),
            ),
            default = '0',
    )

    flip_texcoord_v: BoolProperty(
            name='Flip UV',
            description='Flip TEXCOORD V (vertically) during import.',
            default=False,
    )
    flip_textures_v: BoolProperty(
            name='Flip Textures',
            description='Flip textures vertically during import.',
            default=False,
    )

    flip_winding: BoolProperty(
            name='Flip Winding Order',
            description="Flip face orientation during import. Try if the model doesn't seem to be shading as expected in Blender and enabling the 'Face Orientation' overlay shows **RED** (if it shows BLUE, try 'Flip Normal' instead). Not quite the same as flipping normals within Blender as this only reverses the winding order without flipping the normals.",
            default=False,
    )

    flip_normal: BoolProperty(
            name='Flip Normal',
            description="Flip Normals during import. Try if the model doesn't seem to be shading as expected in Blender and enabling the 'Face Orientation' overlay shows **BLUE** (if it shows RED, try 'Flip Winding Order' instead). Not quite the same as flipping normals within Blender as this won't reverse the winding order",
            default=False,
    )

    # load_all: BoolProperty(
    #         name='Merge All Files',
    #         description='Import all files in the same folder automatically.',
    #         default=True,
    # )

    enable_nun_nodes: BoolProperty(
            name='Import NUN Meshes',
            description='Import meshes with physique properties as standard meshes, using standard bones. Experimental.',
            default=True,
    )

    merge_meshes: BoolProperty(
            name='Merge meshes together',
            description='Merge all selected meshes together into one object.', # WIP: Meshes must be related ?
            default=False,
    )

        # pose_cb_step: IntProperty(
    #         name='Vertex group step',
    #         description='If used vertex groups are 0,1,2,3,etc specify 1. If they are 0,3,6,9,12,etc specify 3.',
    #         default=1,
    #         min=1,
    # )
    # WIP: Needs scale option

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text='Level Of Detail:')
        box.prop(self, 'all_lod')
        # One way to do it
        row = box.row()
        row.enabled = not self.all_lod
        row.prop(self, 'lod')

        box = layout.box()
        box.label(text='Import Options:')
        box.prop(self, 'flip_texcoord_v')
        box.prop(self, 'flip_textures_v')
        box.prop(self, 'flip_winding')
        box.prop(self, 'flip_normal')
        # row = box.row() # probably doesn't make a difference
        box.prop(self, 'enable_nun_nodes')
        box.prop(self, 'merge_meshes')
        # box.prop(self, 'pose_cb_step')

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filepath', 'files','filter_glob'))
        first_file = Path(self.filepath)
        for nextfile in self.files:
            input_file = first_file.parent / nextfile.name
            # Textures need to be written to disk. Assuming textures are in the same folder already
            # new_collection = bpy.data.collections.new(input_file.stem)
            # view_layer = context.view_layer
            # active_collection = view_layer.active_layer_collection.collection
            # active_collection.children.link(new_collection)
            try:
                if input_file.suffix.upper() == '.ZL_':
                    ImportZ(self, context, input_file, **keywords)
                elif input_file.suffix.casefold() == '.bin':
                    ImportB(self, context, input_file, **keywords)
                elif input_file.suffix.casefold() in ('.g1m', '.g1t', '.g1a', '.g2a'):
                    ImportG(self, context, input_file.read_bytes(), (0,), input_file, **keywords)
            except DialogueError as e:
                self.report({'ERROR'}, f"'{input_file}': \n{e}")
                raise

        return {'FINISHED'} # Lets Blender know the operator finished successfully.
        # WIP: pose_path is the 3dmigoto dump object with the skeleton, but it seems like it should be a Blender pose file?

"""Other way to do it.
class OptionsPanelLOD(object):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_parent_id = 'FILE_PT_operator'
    # bl_options = {'DEFAULT_CLOSED'}
    bl_label = ''
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        operator = context.space_data.active_operator
        return operator.bl_idname == 'IMPORT_MUA3_Option_Panel'

    def draw(self, context):
        operator = context.space_data.active_operator
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        self.layout.enabled = not operator.all_lod
        self.layout.prop(operator, 'lod')
"""


# =================================================================
# Main Functions
# =================================================================

def ImportZ(op, context, input_file: Path, **kwargs):
    if input_file.with_suffix('').suffix.casefold() == '.bin':
        data = un_pack(input_file)
        ImportG(op, context, data, get_offsets(data), input_file, **kwargs)
    else:
        ImportG(op, context, un_pack(input_file), (0,), input_file, **kwargs)

def ImportB(op, context, input_file: Path, **kwargs):
    data = input_file.read_bytes()
    ImportG(op, context, data, get_offsets(data), input_file, **kwargs)

def ImportG(op, context, data: bytes, offsets: tuple, input_file: Path,
            flip_textures_v: bool, **kwargs):
    # Assuming all selected files are in the same folder
    file_count = len(offsets)
    for i, pos in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < file_count else None
        e = setEndianMagic(data[pos:pos + 12].split(b'\x00')[0])
        match e:
            case '.g1t':
                g1t_to_dds(data[pos:end], input_file.parent, flip_textures_v)
            case '.g1m':
                Import(op, context, data, pos, input_file, **kwargs)
            case '.g1a':
                pass # WIP
            case '.g2a':
                pass # WIP
            case _:
                msg = f"Detected format '{e}' is not supported."
                op.report({'WARNING'}, msg)

def Import(blender_operator, context, data: bytes, pos: int, input_file: Path,
            all_lod: bool, lod: str, # or is it int?
            flip_texcoord_v: bool = True, flip_winding: bool = False, flip_normal: bool = False,
            enable_nun_nodes: bool = False, merge_meshes: bool = False,
            axis_forward: str = '-Z', axis_up: str = 'Y'):
            # WIP: Possibly dedicated skeleton path, to be chosen by the user
    g1mHeader = G1MHeader(*unpack_from(E+III_STRUCT, data, pos + 12))
    pos += g1mHeader.firstChunkOffset
    global SKELETON_INTERNAL_INDEXP1
    for _ in range(g1mHeader.chunkCount):
        header = GResourceHeader(*unpack_from(E+'4s2I', data, pos))
        # IS_G1MS_UNORDERED = header.chunkVersion < 0x30303332 # WIP?
        magic = GUST_MAGICS[header.magic] if E == '<' else header.magic.decode()
        if magic == 'G1MG':
            G1MGs.append(pos)
        elif magic == 'G1MM':
            # G1MMs.append(G1MM(data, pos)) # WIP: No code to rely on
            pass
        elif magic == 'G1MS' and not SKELETON_INTERNAL_INDEXP1:
            # WIP: Better check if skeleton exists already or update it
            # WIP: If there are multiple skeletons, they seem to be different poses (bHasParsedG1MS if use them all?)
            pass # for testing
            # skel = G1MS(data, pos, header.chunkVersion)
            # G1MSs.append(skel)
            # if skel.bIsInternal:
            #     SKELETON_INTERNAL_INDEXP1 = len(G1MSs)
        elif enable_nun_nodes:
            if magic == 'NUNO':
                NUNOs.append(NUNO(data, pos))
            elif magic == 'NUNV':
                NUNVs.append(NUNV(data, pos))
            elif magic == 'NUNS':
                NUNSs.append(NUNS(data, pos))
            elif magic == 'SOFT':
                # WIP: SOFTs.append(SOFT(data[pos:pos + header.chunkSize])) # WIP: append or process?
                pass
        # Skipping other sections, like EXTR
        pos += header.chunkSize

    global_matrix = axis_conversion(from_forward=axis_forward, from_up=axis_up).to_4x4()
    if input_file.stem not in bpy.data.collections:
        bpy.data.collections.new(input_file.stem)

    for i, pos in enumerate(G1MGs):
        g1mg = G1MG(*unpack_from(f'{E} 4s2I{G1MG_HEADER_STRUCT}', data, pos), data, pos)
        for group in g1mg.meshGroups:
            if not all_lod and group.LOD != int(lod): continue
            for gmesh in group.meshes:
                for subindex in gmesh.indices:
                    mesh_id = f'{i}_{subindex}_{group.LOD}'
                    if mesh_id in MESHES_ADDED: continue # it seems like some meshes are duplicates | we could add a skip_nun_meshes option here
                    MESHES_ADDED.append(mesh_id)
                    submesh = g1mg.submeshes[subindex]
                    # WIP: It seems like for merge, we'd have to merge meshes before adding them to Blender
                    submesh_name = f'{input_file.stem}_{i}_submesh_{subindex}_LOD{group.LOD}'
                    # WIP: NUN
                    # NUNID = -1
                    # gmesh.meshType
                    # gmesh.externalID
                    
                    # Possible WIP: No fallback (import_faces_from_vb) if no ib found.
                    ib = g1mg.index_buffers[submesh.indexBufferIndex]
                    ixb = np.frombuffer(data[ib.offset:ib.offset + ib.count * ib.bitwidth], ib.npDataType) # Alt: unpack_from(f'{E} {ib.count}{ib.npDataType.char}', data, ib.offset), but making np.array from this is not an option (too slow)
                    match submesh.indexBufferPrimType:
                        case 1: # pointlist WIP
                            # assert(all(ibx == range(ib.count))) WIP
                            # assert(len(vb) == ib.count) # WIP
                            # face_sz = ???
                            blender_operator.report({'WARNING'}, f'{submesh_name}: Not imported. Index buffer primitive type pointlist is not supported.')
                            continue
                        case 3: # trianglelist
                            indx_count = ib.count
                            face_count = indx_count // 3
                            # face_sz = 3
                            if flip_winding: ixb = np.reshape(ixb, (-1,3))
                        case 4: # trianglestrip
                            face_count = ib.count - 2
                            indx_count = face_count * 3
                            # face_sz = 3
                            # https://learn.microsoft.com/en-us/windows/win32/direct3d9/triangle-strips
                            sm = np.arange(1, face_count, 2)
                            ixb = np.array([ixb[:-2], ixb[1:-1], ixb[2:]])
                            ixb[2, sm], ixb[1, sm] = ixb[1, sm], ixb[2, sm] # change order at uneven faces
                            ixb = ixb.T if flip_winding else ixb.T.flatten()
                        case _:
                            # linestrip?
                            blender_operator.report({'WARNING'}, f'{submesh_name}: Not imported. Index buffer primitive type {submesh.indexBufferPrimType} is not supported.')
                            continue

                    mesh = bpy.data.meshes.new(submesh_name)
                    obj = bpy.data.objects.new(submesh_name, mesh) # Others then use: mesh: bpy.types.Mesh = obj.data
                    obj.matrix_world = global_matrix # Would G1MM come into play, here?
                    # Custom properties can be attached to obj, e.g. obj[MUA3:unknown] = submesh.unknown
                    mesh.loops.add(indx_count)
                    mesh.polygons.add(face_count)
                    mesh.polygons.foreach_set('loop_start', range(0, indx_count, 3)) # WIP: Can it be a range (or generator)?
                    mesh.polygons.foreach_set('loop_total', [3] * face_count)
                    mesh.loops.foreach_set('vertex_index', np.fliplr(ixb).flatten() if flip_winding else ixb)
                    uv_name = f'MISSING_{mesh_id}' # WIP: (depending on merge)?

                    vbi = submesh.vertexBufferIndex
                    vc = 0
                    blend_indices = [] # using lists, assuming layers correspond with indices
                    blend_weights = []
                    normals = None
                    uv_layer_main = -1 # Could be expanded to all buffers
                    for a in g1mg.vertexAttributeSets[vbi].attributes:
                        # WIP: if NUNID > -1 and remove_physics and a.semantic not in ['POSITION', 'WEIGHTS', 'JOINTS', 'NORMAL', 'COLOR', 'TEXCOORD', 'TANGENT']: continue
                        vb = g1mg.vertex_buffers[g1mg.vertexAttributeSets[vbi].vBufferIndices[a.bufferID]]
                        data_type = G1MGVAFormat(a.dataType)
                        vbuf = data_type.read(data, vb, a.offset // data_type.byte_count)
                        print(f'{data_type.byte_count}x{data_type.size}', vb.count, vb.stride, f'buffer {a.bufferID}:{a.offset}')
                        match a.semantic:
                            case 'POSITION':
                                # WIP: This will cause issues if muliple layers are imported
                                vc = vb.count
                                #if bTRANSLATE_MESHES and root bone translation not 0,0,0, or even if:
                                    # vbuf += np.pad(root bone translation, (0, max(abs(data_type.shape[-1]) - root.shape[-1], 0)))
                                mesh.vertices.add(vc)
                                print(a.layer, data_type.size, vb.count, vc)
                                mesh.vertices.foreach_set('co', vbuf[:,:3].flatten())
                                check_for_4D(mesh, data_type.size, a, vbuf)
                            case 'COLOR':
                                cname = f'COLOR{a.layer}'
                                mesh.vertex_colors.new(name=cname)
                                vbuf = np.pad(vbuf, ((0,0),(0,4 - data_type.size))) # channels should be 4 in Blender 2.80+, size is max 4
                                for l in mesh.loops:
                                    mesh.vertex_colors[cname].data[l.index].color = vbuf[l.vertex_index]
                            case 'NORMAL':
                                if normals is not None:
                                    raise DialogueError(f'{input_file}: Multiple layers of normals in {submesh_name}. Multiple layers are not supported.')
                                check_for_4D(mesh, data_type.size, a, vbuf)
                                if data_type.name[:5] == 'UNORM': vbuf = vbuf * 2.0 - 1.0
                                normals = np.negative(vbuf[:,:3]) if flip_normal else vbuf[:,:3]
                            case 'TANGENT'|'BINORMAL':
                                # mesh.loops[i].tangent is read only
                                blender_operator.report({'INFO'}, f'{submesh_name}: {a.semantic} not imported, in favour of recalculating on export.')
                            case 'JOINTS':
                                blend_indices.append(vbuf)
                            case 'WEIGHTS':
                                print(a.layer, data_type.size, vb.count)
                                blend_weights.append(vbuf)
                            case 'TEXCOORD':
                                csz = data_type.size
                                for x in range(0, csz, 2):
                                    uv_name = f'TEXCOORD{a.layer}.{"xyzw"[:csz][x:][:2]}_{mesh_id}'
                                    mesh.uv_layers.new(name=uv_name)
                                    if csz % 2:
                                        uvs = np.pad(vbuf[:,x:x + 1], ((0,0),(0,1)))
                                    elif flip_texcoord_v:
                                        uvs = 1.0 - vbuf[:,x:x + 2]
                                        # Record that V was flipped so we know to undo it when exporting:
                                        obj[f'MUA3:{uv_name}'] = {'flip_v': True}
                                    else:
                                        uvs = vbuf[:,x:x + 2]
                                    for l in mesh.loops:
                                        mesh.uv_layers[uv_name].data[l.index].uv = uvs[l.vertex_index]
                                if uv_layer_main < 0: uv_layer_main = a.layer
                                uv_name = f'TEXCOORD{uv_layer_main}.{"xyzw"[:csz][:2]}_{mesh_id}'
                            case _:
                                buffer_to_va(mesh, a, vbuf)

                    # WIP: Combine with Armature?
                    # Vertex group method taken from 3Dmigoto plugin. Other solutions might be better.
                    assert(len(blend_indices) == len(blend_weights))
                    for ix in range(np.max(blend_indices) + 1):
                        obj.vertex_groups.new(name=str(ix)) # WIP: this name should be referring to the bones?
                    for lay, blend_i in enumerate(blend_indices):
                        d = blend_i.shape[-1] - blend_weights[lay].shape[-1]
                        blend_w = np.pad(blend_weights[lay], ((0, 0),(0, d)), pad_weights) if d > 0 else blend_weights[lay]
                        # Note: zip shortens the indices if d is negative
                        for vertex in mesh.vertices: # we could add a import_cloth_weights option here
                            # layers seem to replace each other, but I'm not sure
                            for ix, w in zip(blend_i[vertex.index], blend_w[vertex.index]):
                                if not w == 0.0:
                                    obj.vertex_groups[ix].add((vertex.index,), w, 'REPLACE')

                    # Apply Normals
                    mesh.validate(verbose=False, clean_customdata=False)
                    mesh.update() # Might not be needed
                    mesh.normals_split_custom_set_from_vertices(normals)
                    # mesh.use_auto_smooth = True

                    # TEXTURES | WIP: How to link the mesh to the material?
                    if g1mg.materials:
                        # Note: G1MG materials don't seem to have unique identifiers.
                        gmatID = f'Mat_{mesh_id}'
                        # Materials should be per mesh, because they're linked to the UV
                        # gtexs = g1mg.materials[submesh.materialIndex].g1mgTextures
                        # gmatID = f'Material_{'-'.join(str(t.index) for t in gtexs)}'
                        material = bpy.data.materials.new(gmatID)
                        material.use_nodes = True
                        metlRough = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled') # What are my options?, 'ShaderNodeGroup', etc.
                        ouputNode = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
                        metlRough.location = 10, 300
                        ouputNode.location = 300, 300
                        material.node_tree.links.new(metlRough.outputs[0], ouputNode.inputs[0]) # 'Shader', 'Surface' ?

                        for tex in g1mg.materials[submesh.materialIndex].g1mgTextures:
                            tex_name = f'{tex.index:04d}.dds'
                            tex_path = input_file.parent / tex_name
                            imageNode = material.node_tree.nodes.new('ShaderNodeTexImage')
                            if tex_name in bpy.data.images:
                                # WIP: Might need a more unique name for images and gmatID | Not sure if the if .. in logic works here
                                # Update: Actually, it seems like the material holds UV information, which should vary per mesh, so we might not need this
                                imageNode.image = bpy.data.images[tex_name]
                            elif tex_path.is_file():
                                imageNode.image = bpy.data.images.load(filepath=str(tex_path), check_existing=True)
                            else:
                                # WIP: Can we get the dimensions from tex?
                                imageNode.image = bpy.data.images.new(name=tex_name, width=1024, height=1024,
                                                                      alpha=True, float_buffer=False)
                                imageNode.image.source = 'FILE'
                                imageNode.image.filepath = str(tex_path)
                            # Alternatively, load an image from bytes:
                            # imageNode.image = bpy.data.images.new(tex_name, 8, 8) # dummy w, h
                            # imageNode.image.pack(data=data, data_len=len(data))
                            # imageNode.image.source = 'FILE'
                            imageNode.image.name = tex_name
                            imageNode.image.alpha_mode = 'CHANNEL_PACKED'
                            # Alternative for UV, but it seems to be incomplete
                            # mapCoNode = material.node_tree.nodes.new('ShaderNodeMapping')
                            # coordNode = material.node_tree.nodes.new('ShaderNodeTexCoord') # location ?
                            # material.node_tree.links.new(coordNode.outputs['UV'], mapCoNode.inputs['Surface'])
                            mapCoNode = material.node_tree.nodes.new('ShaderNodeUVMap')
                            mapCoNode.uv_map = uv_name
                            material.node_tree.links.new(imageNode.inputs[0], mapCoNode.outputs[0]) # 'Vector' both? (should be 'UV' on ShaderNodeUVMap)
                            match tex.textureType:
                                case 1: # and not bHasDiffuse
                                    imageNode.label = 'Diffuse'
                                    x, y = -200, 460
                                    material.node_tree.links.new(metlRough.inputs['Base Color'], imageNode.outputs['Color'])
                                    # Assuming Opaque Diffuse:
                                    # metlRough.inputs['Alpha'].default_value = 1
                                    # metlRough.inputs['Alpha'] = None
                                    # else: material.node_tree.links.new(imageNode.outputs['Alpha'], metlRough.inputs['Alpha'])
                                    # WIP: Mix in vertex colours blender-4.2.0-windows-x64\4.2\scripts\addons_core\io_scene_gltf2\blender\imp\gltf2_blender_pbrMetallicRoughness.py#L667
                                    metlRough.inputs['Metallic'].default_value = 0.0
                                    metlRough.inputs['Roughness'].default_value = 1.0
                                    # {'index' : idx, 'texCoord': tex.layer}, # idx is probably unimportant, but texCoord is important
                                    # if tex.layer == 1: pass # UV1?
                                case 2:
                                    imageNode.label = 'Emissive'
                                    x, y = -200, -460
                                    material.node_tree.links.new(metlRough.inputs['Emission Color'], imageNode.outputs['Color'])
                                    # metlRough.inputs['Emission Strength'].default_value = 0
                                case 3:
                                    imageNode.label = 'Normal Map'
                                    x, y = -200, 0
                                    normal = material.node_tree.nodes.new('ShaderNodeNormalMap')
                                    normal.location = x - 150, y - 40
                                    normal.uv_map = uv_name
                                    normal.inputs['Strength'].default_value = 1
                                    material.node_tree.links.new(metlRough.inputs['Normal'], normal.outputs['Normal'])
                                    material.node_tree.links.new(normal.inputs['Color'], imageNode.outputs['Color'])
                                case 5:
                                    imageNode.label = 'Occlusion'
                                    x, y = -200, -920
                                    # Making new group, not using metl Roughness material, for the purpose of saving the material for export
                                    occlNode = material.node_tree.nodes.new('ShaderNodeGroup') # What are my options?, 'ShaderNodeGroup', etc.
                                    occlNode.node_tree = bpy.data.node_groups[gmatID] if gmatID in bpy.data.node_groups else \
                                                         create_mat_node_group(gmatID)
                                    occlNode.location = 240, y
                                    occlNode.width = 180
                                    node = material.node_tree.nodes.new('ShaderNodeSeparateColor')
                                    node.location = x, y - 75
                                    imageNode.image.colorspace_settings.is_data = True
                                    material.node_tree.links.new(occlNode.inputs['Occlusion'], node.outputs['Red'])
                                    material.node_tree.links.new(node.inputs[0], imageNode.outputs['Color'])
                                case _:
                                    # Specular blender-4.2.0-windows-x64\4.2\scripts\addons_core\io_scene_gltf2\blender\imp\gltf2_blender_pbrMetallicRoughness.py#L317
                                    print(f'Unhandled texture type: {tex.textureType}')
                            mapCoNode.location = x - 500, y - 70
                            imageNode.location = x - 240, y
                            # imageNode.image.interpolation = 'Linear' # or 'Closest' ? IDK what this could be based on
                            imageNode.extension = 'REPEAT' # (10497) or 'EXTEND' (slightly better errors near the edge), 'MIRROR', IDK, how to interpret tex.tileModeX / tex.tileModeY
                            # if wraps are not equal:
                            # mapCoNod1 = material.node_tree.nodes.new('ShaderNodeCombineXYZ')
                            # mapCoNod2 = material.node_tree.nodes.new('ShaderNodeSeparateXYZ')
                            # mapCoNod2.location = x - 880, y - 100 # but xy adjusted already
                            # mapCoNod1.location = x - 480, y - 100 # but xy adjusted already
                            # for uv in range(2):
                            #     # if 'EXTEND': no math, just do (mapCoNod1.inputs[uv], mapCoNod2.outputs[uv])
                            #     math = material.node_tree.nodes.new('ShaderNodeMath')
                            #     math.location = x - 680, y + 30 - uv * 200 # but xy adjusted already
                            #     math.operation = 'WRAP'
                            #     math.inputs[1].default_value = 0
                            #     math.inputs[2].default_value = 1
                            #     material.node_tree.links.new(mapCoNod1.inputs[uv], math.outputs[0])
                            #     material.node_tree.links.new(math.inputs[0], mapCoNod2.outputs[uv])
                            # mapCoNode.location = x - 1100, y - 70 # but xy adjusted already
                            # material.node_tree.links.new(imageNode.inputs[0], mapCoNode.outputs[0]) # 'Vector' both?
                        # if useAlpha: material.blend_method = 'BLEND' # WIP: Where to get this info?
                        material.surface_render_method = 'DITHERED' # 'BLEND' if useAlpha
                        # material.node_tree.nodes.clear() # ?
                        obj.data.materials.append(material)

                    print('works')
                    # bpy.data.scenes[0].collection.objects.link(obj)
                    bpy.data.collections[input_file.stem].objects.link(obj)
                    # link_object_to_scene(context, obj)

                    # WIP: Skeleton as poses
                    # if pose_path:
                    #     import_pose(operator, context, pose_path, limit_bones_to_vertex_groups=True,
                    #             axis_forward=axis_forward, axis_up=axis_up,
                    #             pose_cb_off=pose_cb_off, pose_cb_step=pose_cb_step)
                    #     set_active_object(context, obj)
    context.scene.collection.children.link(bpy.data.collections[input_file.stem])


def check_for_4D(mesh, size: int, a: G1MGVertexAttribute, buf: np.ndarray):
    """Checks if the buffer has 4 dimensions and saves the 4th one to vertex attributes."""
    if size == 4 and any(buf[:,3] != 1.0):
        buffer_to_va(mesh, a, buf[:,3], '.w')

def buffer_to_va(mesh, a: G1MGVertexAttribute, buf: np.ndarray, suffix: str = ''):
    """Saves a vertex buffer to vertex attributes."""
    if 3 < a.dataType > 10 or a.dataType == 0xFF:
        buf = buf.astype('int32')
        btype = 'INT'
    else:
        btype = 'FLOAT'
    battribute = mesh.attributes.new(name=f'{a.semantic}{suffix}', type=btype, domain='POINT')
    for v in mesh.vertices:
        battribute.data[v.index].value = buf[v.index]
    # blender_operator.report({'WARNING'}, f'{submesh_name}: {a.semantic} stored in vertex attributes. Beware that some types of edits on this mesh may be problematic.')

def create_mat_node_group(name: str):
    """
    Make a Group node with a hookup for Occlusion. No effect in Blender, but
    used to tell the exporter what the occlusion map should be.
    """
    # Note: taken from glTF default import gltf2_blender_material_helpers.py
    node_group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    node_group.interface.new_socket('Occlusion', socket_type='NodeSocketFloat')
    node_group.nodes.new('NodeGroupOutput')
    node_group_input = node_group.nodes.new('NodeGroupInput')
    # node_group_input.location = -200, 0
    return node_group

def pad_weights(vector: np.ndarray, pad_width: tuple, iaxis: int, kwargs: dict):
    """Numpy pad function, which right pads a weight 2D array to normalize the sum to 1.0, if less."""
    if iaxis == 1:
        vector[-pad_width[1]:] = np.clip((1.0 - sum(vector)) / pad_width[1], 0.0, 1.0)


# def menu_func(self, context):
#     self.layout.operator(MUA3_Gust_Import.bl_idname)
# 
# def register():
#     bpy.utils.register_class(MUA3_Gust_Import)
#     bpy.types.TOPBAR_MT_file_import.append(menu_func)  # Adds the new operator to an existing menu.
# 
# def unregister():
#     bpy.utils.unregister_class(MUA3_Gust_Import)
#     bpy.types.TOPBAR_MT_file_import.remove(menu_func)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
# if __name__ == "__main__":
#     register()