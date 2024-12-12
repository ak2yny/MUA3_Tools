# Based primarily off of:
#   - https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
#   - https://github.com/eArmada8/gust_stuff
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html

import numpy as np
from pathlib import Path
from struct import unpack_from

# Project
from .lib.lib_g1m import G1MGVertexAttribute, G1MHeader, G1MG, G1MG_HEADER_STRUCT, G1MGVAFormat, G1MS # *, G1MM, make_nun_bones, calc_abs_rotation_position, compute_center_of_mass
from .lib.lib_g1t import g1t_to_dds
from .lib.lib_gust import *
from .lib.lib_nun import NUNO, NUNV, NUNS
from .lib.lib_oid import GLOBAL2OID, OID
from .MUA3_BIN import get_offsets
from .MUA3_Formats import GUST_MAGICS
from .MUA3_G1_Helper import setEndianMagic
from .MUA3_ZL import un_pack

# Blender
import bpy
from bpy_extras.io_utils import axis_conversion, ImportHelper, orientation_helper
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, StringProperty # , IntProperty
from mathutils import Matrix, Quaternion, Vector


# Settings:
MESHES_ADDED, G1MGs, G1MMs, G1MSs, NUNOs, NUNVs, NUNSs, SOFTs = ([] for _ in range(8))
SKELETON_INTERNAL_INDEXP1 = 0


# =================================================================
# Blender import class with options
# =================================================================

# scene = bpy.context.scene

class DialogueError(Exception): pass

@orientation_helper(axis_forward='-Z', axis_up='Y')
class MUA3_Gust_Import(bpy.types.Operator, ImportHelper):
    """Import .g1m 3D objects and associated files from Marvel Ultimate Alliance 3 and other compatible games."""
                                                 # ^^ Use this as a tooltip.
    bl_idname = 'mua3.gust_import'               # Unique identifier.
    bl_label = 'Import Gust Files from MUA3'     # Display name in the interface.
    bl_options = {'PRESET', 'REGISTER', 'UNDO'}  # Enable undo for the operator. WIP: Remove register?

    # For ImportHelper
    filename_ext = '.ZL_' # or .bin, .g1m
    filter_glob: StringProperty(
            default='*.ZL_;*.bin;*.g1m;*.g1t;*.g1a;*.g2a',
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
            default=True,
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

    enable_nun_nodes: BoolProperty(
            name='Import NUN Meshes',
            description='Import meshes with physique properties as standard meshes, using standard bones. Experimental.',
            default=True,
    )

    merge_meshes: BoolProperty(
            name='Merge Meshes',
            description='Merge grouped meshes together into one mesh with information of each submesh.',
            default=True,
    )

    translate_meshes: BoolProperty(
            name='Translate Meshes',
            description='Move mesh origins according to the root bone of the skeleton.',
            default=True,
    )

    scale_objects: FloatProperty(
            name = "Scale",
            description = "Scale the imported objects uniformly.",
            default = 1.0,
            min = 0.0,
            )

    # pose_cb_step: IntProperty(
    #         name='Vertex group step',
    #         description='If used vertex groups are 0,1,2,3,etc specify 1. If they are 0,3,6,9,12,etc specify 3.',
    #         default=1,
    #         min=1,
    # )
    # WIP: Possibly dedicated skeleton path, to be chosen by the user

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text='Level Of Detail:')
        box.prop(self, 'all_lod')
        row = box.row()
        row.enabled = not self.all_lod
        row.prop(self, 'lod')

        box = layout.box()
        box.label(text='Flip Options:')
        box.prop(self, 'flip_texcoord_v')
        box.prop(self, 'flip_textures_v')
        box.prop(self, 'flip_winding')
        box.prop(self, 'flip_normal')
        box = layout.box()
        box.label(text='Mesh Options:')
        box.prop(self, 'enable_nun_nodes')
        box.prop(self, 'merge_meshes')
        box = layout.box()
        box.label(text='Transform Options:')
        box.prop(self, 'translate_meshes')
        box.prop(self, "axis_forward")
        box.prop(self, "axis_up")
        box.prop(self, "scale_objects")
        # box.prop(self, 'pose_cb_step')

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filepath', 'files','filter_glob'))
        global MESHES_ADDED, G1MGs
        first_file = Path(self.filepath)
        for oid in (o.name for o in self.files if o.name[-4:].casefold() == '.oid' or o.name[-7:].casefold() == 'oid.bin'):
            # get bone ids first
            OID((first_file.parent / oid).read_bytes)
        for nextfile in self.files:
            input_file = first_file.parent / nextfile.name
            # Textures need to be written to disk.
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

            MESHES_ADDED, G1MGs = [], [] # , G1MMs, G1MSs, NUNOs, NUNVs, NUNSs, SOFTs = ([] for _ in range(7))


        return {'FINISHED'} # Lets Blender know the operator finished successfully.
        # WIP: pose_path is the 3dmigoto dump object with the skeleton, but it seems like it should be a Blender pose file?


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
                out = input_file.parent / input_file.stem
                g1t_to_dds(data[pos:end], out, flip_textures_v)
                for dds in out.iterdir(): dds.rename(input_file.parent / dds.name)
                out.rmdir()
            case '.g1m':
                ParseG1M(data, pos, kwargs['enable_nun_nodes'])
            case '.g1a':
                pass # WIP
            case '.g2a':
                pass # WIP
            case _:
                op.report({'INFO'}, f"Detected format '{e}' is not supported.")
    Import(op, context, data, input_file, **kwargs)

def ParseG1M(data: bytes, pos: int, enable_nun_nodes: bool):
    g1mHeader = G1MHeader(*unpack_from(E+III_STRUCT, data, pos + 12))
    pos += g1mHeader.firstChunkOffset
    global SKELETON_INTERNAL_INDEXP1
    for _ in range(g1mHeader.chunkCount):
        header = GResourceHeader(*unpack_from(E+'4s2I', data, pos))
        magic = GUST_MAGICS[header.magic] if E == '<' else header.magic.decode()
        if magic == 'G1MG':
            G1MGs.append(pos)
        elif magic == 'G1MM':
            # G1MMs.append(G1MM(data, pos)) # WIP: seems to be connected to bone palette, but how?
            pass
        elif magic == 'G1MS' and not SKELETON_INTERNAL_INDEXP1:
            if header.chunkVersion < 0x30303332:
                # WIP:
                raise DialogueError(f'Unordered skeleton detected. The addon does not support unordered skeletons at this time.')
            # WIP: If there are multiple skeletons, they seem to be different poses
            skel = G1MS(data, pos, header.chunkVersion)
            G1MSs.append(skel)
            if skel.bIsInternal:
                SKELETON_INTERNAL_INDEXP1 = len(G1MSs)
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

def Import(blender_operator, context, data: bytes, input_file: Path,
            all_lod: bool, lod: str,
            flip_texcoord_v: bool = True, flip_winding: bool = False, flip_normal: bool = False,
            enable_nun_nodes: bool = False, merge_meshes: bool = True, translate_meshes: bool = True,
            scale_objects: float = 1.0, axis_forward: str = '-Z', axis_up: str = 'Y'):
    lod = int(lod)
    global_matrix = axis_conversion(from_forward=axis_forward, from_up=axis_up).to_4x4()
    arm_name = f'{input_file.stem}_skel'
    
    col_name = f'{input_file.stem}_LOD{lod}'
    collection = bpy.data.collections[col_name] if col_name in bpy.data.collections else bpy.data.collections.new(col_name)
    collections = context.view_layer.active_layer_collection.collection.children
    if col_name not in collections:
        collections.link(collection)

    if arm_name in bpy.data.armatures:
        global_matrix @= Matrix.Translation(bpy.data.objects[arm_name]['MUA3:ROOT_TRANSLATION'])
    elif SKELETON_INTERNAL_INDEXP1:
        g1ms: G1MS = G1MSs[SKELETON_INTERNAL_INDEXP1 - 1]
        if g1ms.joints:
            a = bpy.data.armatures.new(arm_name)
            a.display_type = 'STICK' # options?
            ao = bpy.data.objects.new(arm_name, a)
            ao.matrix_world = global_matrix
            ao.show_in_front = True
            collection.objects.link(ao)
            context.view_layer.objects.active = ao
            bpy.ops.object.mode_set(mode='EDIT')
            arm = ao.data
            # WIP: For safety, we could add the blender bones beforehand, and change the matrix logic order, which would take care of unordered skeletons
            for global_id, j in enumerate(g1ms.joints):
                # Throws exception if child is attempted to be processed before parent
                # WIP: global_id for naming seems to be wrong. maybe use local_id = g1ms.findGlobalID(global_id), but would have to provide g1ms to other files (or skeleton object)
                bone = arm.edit_bones.new(name=GLOBAL2OID[global_id] if global_id in GLOBAL2OID else f'bone_{global_id}') # g1ms.getName(local_id, GLOBAL2OID) # it seems like I need local_id, not global_id
                mx = Matrix.LocRotScale(j.position, Quaternion(j.rotation), j.scale)
                if j.parentID == 0xFFFFFFFF:
                    if translate_meshes:
                        global_matrix @= Matrix.Translation(j.position)
                        ao['MUA3:ROOT_TRANSLATION'] = j.position
                    j.abs_tm = mx
                    bone.matrix = mx
                else:
                    j.abs_tm = g1ms.joints[j.parentID].abs_tm @ mx
                    bone.matrix = j.abs_tm
                    bone.parent = arm.edit_bones[j.parentID]
                    if global_id not in g1ms.parentIDs:
                        bone.length = 2
                    elif (bone.parent.head - bone.head).length > bone.parent.length:
                        bone.parent.tail = bone.head
                        # if min(abs(x) for x in bone.parent.head.rotation_difference(bone.head).axis) < 0.1:
                        #     bone.parent.tail = bone.head
                        # else:
                        #     bone.parent.length = 0.1
            for bone in arm.edit_bones:
                child_bones = bone.children
                cbc = len(child_bones)
                if cbc == len(bone.children_recursive):
                    if cbc == 1:
                        bone.tail = child_bones[0].head
                    elif cbc > 1:
                        bone.tail = Vector(map(sum, zip(*(b.head.xyz for b in child_bones)))) / cbc
                elif cbc > 1:
                    mcc = (b for b in child_bones if len(b.children_recursive) > 1)
                    cb = next(mcc, None)
                    if cb == None: continue
                    ocb = next(mcc, None)
                    if ocb == None:
                        if not cb.head == bone.tail: bone.tail = cb.head
                    else:
                        bone.tail = Vector(map(sum, zip(*(b.head.xyz for b in child_bones)))) / cbc
            bpy.ops.object.mode_set(mode='OBJECT')

    for i, pos in enumerate(G1MGs):
        g1mg = G1MG(*unpack_from(f'{E} 4s2I{G1MG_HEADER_STRUCT}', data, pos), data, pos)

        for group in g1mg.meshGroups:
            if not all_lod and group.LOD != lod: continue
            for gmesh in group.meshes:
                vbuf: dict[str, np.ndarray] = {}
                blend_indices = [] # using lists, assuming layers correspond with indices
                blend_weights = []
                bone_pal = [g1mg.joint_palettes[g1mg.submeshes[s].bonePaletteIndex].joints for s in gmesh.indices]
                for subenum, subindex in enumerate(gmesh.indices):
                    mesh_id = f'{i}_LOD{group.LOD}_{gmesh.name}_{subindex}'
                    if f'{i}_LOD{group.LOD}_{subindex}' in MESHES_ADDED: continue # it seems like some meshes are duplicates | we could add a skip_nun_meshes option here
                    done = subenum > 0
                    mgdn = merge_meshes and done
                    MESHES_ADDED.append(f'{i}_LOD{group.LOD}_{subindex}')
                    submesh = g1mg.submeshes[subindex]
                    submesh_name = f'{input_file.stem}_{mesh_id}'
                    # WIP: NUN
                    # NUNID = -1
                    # gmesh.meshType
                    # gmesh.externalID
                    if not mgdn: uv_name = f'MISSING_{mesh_id}'
                    ib = g1mg.index_buffers[submesh.indexBufferIndex]
                    if merge_meshes:
                        vbo, ibo = 0, 0
                        vbe = ib.count
                        indx_count = vbe
                    else:
                        vbo = submesh.vertexBufferOffset
                        vbe = vbo + submesh.vertexCount
                        indx_count = submesh.indexCount
                        ibo = submesh.indexBufferOffset
                    if not done:
                        # Note: If there are multiple instances of the same mesh_id (gmesh.indices[0]) in the same file that don't follow each other, this will produce an error or broken mesh
                        ibuf = np.frombuffer(data[ib.offset:ib.offset + ib.count * ib.bitwidth], ib.npDataType) # Alt: unpack_from(f'{E} {indx_count}{ib.npDataType.char}', data, ib.offset), but making np.array from this is not an option (too slow)
                    if not mgdn:
                        ixb = ibuf[ibo:ibo + indx_count]
                        match submesh.indexBufferPrimType:
                            case 1: # pointlist WIP
                                # assert(all(ixb == range(ibc)))
                                # assert(vbe - vbo == ibc)
                                # face_count = ???
                                blender_operator.report({'WARNING'}, f'{submesh_name}: Not imported. Index buffer primitive type "pointlist" is not supported.')
                                continue
                            case 3: # trianglelist
                                face_count = indx_count // 3
                                if flip_winding: ixb = np.reshape(ixb, (-1,3))
                            case 4: # trianglestrip WIP (Untested)
                                face_count = indx_count - 2
                                indx_count = face_count * 3
                                # https://learn.microsoft.com/en-us/windows/win32/direct3d9/triangle-strips
                                sm = np.arange(1, face_count, 2)
                                ixb = np.array([ixb[:-2], ixb[1:-1], ixb[2:]])
                                ixb[2, sm], ixb[1, sm] = ixb[1, sm], ixb[2, sm] # change order at uneven faces
                                ixb = ixb.T if flip_winding else ixb.T.flatten()
                            case _:
                                # linestrip?
                                blender_operator.report({'WARNING'}, f'{submesh_name}: Not imported. Index buffer primitive type {submesh.indexBufferPrimType} is not supported.')
                                continue

                        if flip_winding: ixb = np.fliplr(ixb).flatten()
                        mesh = bpy.data.meshes.new(submesh_name)
                        obj = bpy.data.objects.new(submesh_name, mesh)
                        obj.matrix_world = global_matrix # Would G1MM come into play, here?
                        mesh.loops.add(indx_count)
                        mesh.polygons.add(face_count)
                        mesh.polygons.foreach_set('loop_start', range(0, indx_count, 3))
                        mesh.polygons.foreach_set('loop_total', [3] * face_count)
                        mesh.loops.foreach_set('vertex_index', ixb - vbo)

                    for a in g1mg.vertexAttributeSets[submesh.vertexBufferIndex].attributes:
                        if mgdn: continue
                        data_type = G1MGVAFormat(a.dataType)
                        sem = a.semantic if a.semantic in ('NORMAL', 'POSITION') else f'{a.semantic}{a.layer}' # could add more semantics, if they don't support layers
                        # WIP: if NUNID > -1 and remove_physics and a.semantic not in ['POSITION', 'WEIGHTS', 'JOINTS', 'NORMAL', 'COLOR', 'TEXCOORD', 'TANGENT']: continue
                        # WIP: Assuming identical buffers on mesh groups.
                        if done:
                            if a.semantic in ('JOINTS', 'WEIGHTS'): continue
                        else:
                            if sem in vbuf:
                                raise DialogueError(f'{input_file}: Multiple layers of {sem} in {submesh_name}. Multiple layers are not supported.')
                            vb = g1mg.vertex_buffers[g1mg.vertexAttributeSets[submesh.vertexBufferIndex].vBufferIndices[a.bufferID]]
                            vbuf[sem] = data_type.read(data, vb, a.offset // data_type.byte_count)
                            if merge_meshes: vbe = vb.count
                        match a.semantic:
                            case 'POSITION':
                                #if bTRANSLATE_MESHES and root bone translation not 0,0,0, or even if:
                                    # vbuf[:,1] += Z_offset # must be writeable
                                mesh.vertices.add(vbe - vbo)
                                mesh.vertices.foreach_set('co', vbuf[sem][vbo:vbe,:3].flatten())
                                check_for_4D(mesh, data_type.size, a, vbuf[sem][vbo:vbe,:])
                            case 'COLOR':
                                if not done: vbuf[sem] = np.pad(vbuf[sem], ((0,0),(0,4 - data_type.size))) # channels should be 4 in Blender 2.80+, size is max 4
                                veco = mesh.vertex_colors.new(name=f'COLOR{a.layer}')
                                for li, lvi in enumerate(ixb):
                                    veco.data[li].color = vbuf[sem][lvi]
                            case 'NORMAL':
                                if data_type.name[:5] == 'UNORM' and not done: vbuf[sem] = vbuf[sem] * 2.0 - 1.0
                                check_for_4D(mesh, data_type.size, a, vbuf[sem][vbo:vbe,:])
                                normals = np.negative(vbuf[sem][vbo:vbe,:3]) if flip_normal else vbuf[sem][vbo:vbe,:3]
                            case 'TANGENT'|'BINORMAL':
                                # mesh.loops[i].tangent is read only
                                blender_operator.report({'INFO'}, f'{submesh_name}: {a.semantic} not imported, in favour of recalculating on export.')
                            case 'JOINTS':
                                if len(blend_indices) > 1:
                                    buffer_to_va(mesh, a, vbuf[sem], f'{a.layer}_TYPE{submesh.submeshType}')
                                else:
                                    blend_indices.append(vbuf[sem])
                            case 'WEIGHTS':
                                if len(blend_weights) > 1: # or a.layer > 0?
                                    buffer_to_va(mesh, a, vbuf[sem], f'{a.layer}_TYPE{submesh.submeshType}')
                                    blender_operator.report({'INFO'}, f'{submesh_name}: {sem} for type {submesh.submeshType} (physics?) not processed. Data written to custom properties.')
                                else:
                                    blend_weights.append(vbuf[sem])
                            case 'TEXCOORD':
                                csz = data_type.size
                                if csz % 2 and not done: vbuf[sem] = np.pad(vbuf[sem], ((0,0),(0,1)))
                                for x in range(0, csz, 2):
                                    uv_name = f'TEXCOORD{a.layer}.{"xyzw"[x:x + 2]}_{mesh_id}'
                                    uvs = np.copy(vbuf[sem][:,x:x + 2])
                                    if flip_texcoord_v:
                                        uvs[:,1] = 1.0 - uvs[:,1]
                                        # Record that V was flipped so we know to undo it when exporting:
                                        obj[f'MUA3:{uv_name}'] = {'flip_v': True}
                                    veuv = mesh.uv_layers.new(name=uv_name)
                                    for li, lvi in enumerate(ixb):
                                        veuv.data[li].uv = uvs[lvi]
                                uv_name = f'TEXCOORD{a.layer}.xy_{mesh_id}' # Never apply materials to zw
                            case _:
                                buffer_to_va(mesh, a, vbuf[sem][vbo:vbe,:])

                    if merge_meshes and subenum > 0: # or len(gmesh.indices) > 1
                        fo = submesh.indexBufferOffset * face_count // ib.count
                        fe = fo + submesh.indexCount * face_count // ib.count # min(fe, face_count)
                        for p in mesh.polygons[fo:fe]:
                            p.material_index = subenum

                    # Apply Weights
                    # we could add a import_cloth_weights option here
                    assert(len(blend_indices) == len(blend_weights))
                    o = submesh.vertexBufferOffset
                    e = o + submesh.vertexCount
                    bone_pal = g1mg.joint_palettes[submesh.bonePaletteIndex].joints
                    for lay, blend_i in enumerate(blend_indices):
                        d = blend_i.shape[-1] - blend_weights[lay].shape[-1]
                        assert(not d < 0)
                        blend_w = np.pad(blend_weights[lay][o:e], ((0, 0),(0, d)), pad_weights) if d > 0 else blend_weights[lay][o:e]
                        blend_i = blend_i[o:e]
                        if lay > 0:
                            # WIP: Physics? global_id = bone_pal[ix // 3].physicsIndex
                            # submesh.submeshType 53: normal record?
                            # submesh.submeshType 61: hair (incl. all facial) > Particle system, hair & hair dynamics, add vertex group (type?)
                            continue
                        for bi in range(blend_i.shape[0]):
                            vi = bi + o if merge_meshes else bi
                            for ix, w in zip(blend_i[bi], blend_w[bi]):
                                if w != 0.0:
                                    if ix % 3:
                                        vgnm = f'unused_{subenum}_{bi}'
                                    else:
                                        global_id = bone_pal[ix // 3].jointIndex # can 3 be taken from the g1mg?
                                        vgnm = GLOBAL2OID[global_id] if global_id in GLOBAL2OID else \
                                               f'bone_{global_id}'
                                    vg = obj.vertex_groups[vgnm] if vgnm in obj.vertex_groups else \
                                         obj.vertex_groups.new(name=vgnm)
                                    vg.add((mesh.vertices[vi].index,), w, 'REPLACE') # layers seem to replace each other, but I'm not sure

                    # Apply Normals
                    if not mgdn:
                        mesh.validate(verbose=False, clean_customdata=False)
                        mesh.normals_split_custom_set_from_vertices(normals)

                    # TEXTURES | WIP: How to link the mesh to the material?
                    if g1mg.materials:
                        x, yu = -400, -1380
                        # Note: G1MG materials don't seem to have unique identifiers.
                        # Materials should be per mesh, because they're linked to the UV
                        gmatID = f'Mat_{mesh_id}'
                        # gtexs = g1mg.materials[submesh.materialIndex].g1mgTextures
                        # gmatID = f'Material_{'-'.join(str(t.index) for t in gtexs)}'
                        material = bpy.data.materials.new(gmatID)
                        material.use_nodes = True
                        metlRough = material.node_tree.nodes[0]
                        # Alternatively:
                        # material.node_tree.nodes.clear()
                        # metlRough = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled') # 'ShaderNodeGroup' (output 'Shader'), etc.
                        # ouputNode = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
                        # metlRough.location = 10, 300
                        # ouputNode.location = 300, 300
                        # material.node_tree.links.new(metlRough.outputs[0 aka 'BSDF'], ouputNode.inputs[0 aka 'Surface'])
                        mapCoNode = material.node_tree.nodes.new('ShaderNodeUVMap')
                        mapCoNode.uv_map = uv_name
                        mapCoNode.location = x - 800, 300
                        # Alternative for UV, but it seems to be incomplete
                        # mapCoNode = material.node_tree.nodes.new('ShaderNodeMapping')
                        # coordNode = material.node_tree.nodes.new('ShaderNodeTexCoord') # location ?
                        # material.node_tree.links.new(coordNode.outputs['UV'], mapCoNode.inputs['Surface']) # mapCoNode.outputs['Vector']

                        for tex in g1mg.materials[submesh.materialIndex].g1mgTextures:
                            tex_name = f'{tex.index:04d}.dds'
                            tex_path = input_file.parent / tex_name
                            imageNode = material.node_tree.nodes.new('ShaderNodeTexImage')
                            if tex_name in bpy.data.images:
                                # WIP: Might need a more unique name for images and gmatID | Not sure if the if .. in logic works here
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
                            material.node_tree.links.new(imageNode.inputs[0], mapCoNode.outputs[0]) # 'UV' to 'Vector'
                            match tex.textureType:
                                case 0:
                                    imageNode.label = 'Specular'
                                    y = -460
                                    # hook factor in between: blender-4.2.0-windows-x64\4.2\scripts\addons_core\io_scene_gltf2\blender\imp\gltf2_blender_material_utils.py#L108
                                    imageNode.image.colorspace_settings.is_data = True
                                    material.node_tree.links.new(metlRough.inputs['Specular Tint'], imageNode.outputs['Color'])
                                case 1:
                                    imageNode.label = 'Diffuse'
                                    y = 920
                                    material.node_tree.links.new(metlRough.inputs['Base Color'], imageNode.outputs['Color'])
                                    # Opaque Diffuse is standard:
                                    # if Alpha: material.node_tree.links.new(imageNode.outputs['Alpha'], metlRough.inputs['Alpha'])
                                    # metlRough.inputs['Roughness'].default_value = 1.0 # default 0.5
                                    # Mix in vertex colours? blender-4.2.0-windows-x64\4.2\scripts\addons_core\io_scene_gltf2\blender\imp\gltf2_blender_pbrMetallicRoughness.py#L667
                                    # {'index' : idx, 'texCoord': tex.layer}, # idx is probably unimportant, but texCoord is important
                                case 2:
                                    imageNode.label = 'R: Spec. Refl. - B: Metal/Env. - G: Unk.'
                                    y = 460
                                    node = material.node_tree.nodes.new('ShaderNodeSeparateColor')
                                    node.location = x + 140, y - 200
                                    material.node_tree.links.new(node.inputs['Color'], imageNode.outputs['Color'])
                                    material.node_tree.links.new(metlRough.inputs['Specular IOR Level'], node.outputs['Red']) # or inverse and as roughness?
                                    material.node_tree.links.new(metlRough.inputs['Metallic'], node.outputs['Blue'])
                                    # material.node_tree.links.new(metlRough.inputs['UNKNOWN'], node.outputs['Green'])
                                case 3:
                                    imageNode.label = 'Normal Map'
                                    y = 0
                                    normal = material.node_tree.nodes.new('ShaderNodeNormalMap')
                                    normal.location = x + 140, y + 100
                                    normal.uv_map = uv_name
                                    normal.inputs['Strength'].default_value = 1
                                    material.node_tree.links.new(metlRough.inputs['Normal'], normal.outputs['Normal'])
                                    material.node_tree.links.new(normal.inputs['Color'], imageNode.outputs['Color'])
                                case 5:
                                    imageNode.label = 'Occlusion'
                                    y = -920
                                    # Maybe this could work: https://youtu.be/AguPCHZuF88
                                    # Making new group, not using metl Roughness material, for the purpose of saving the material for export
                                    occlNode = material.node_tree.nodes.new('ShaderNodeGroup') # What are my options?, 'ShaderNodeGroup', etc.
                                    occlNode.node_tree = bpy.data.node_groups[gmatID] if gmatID in bpy.data.node_groups else \
                                                         create_mat_node_group(gmatID)
                                    occlNode.location = x + 340, y
                                    occlNode.width = 180
                                    node = material.node_tree.nodes.new('ShaderNodeSeparateColor')
                                    node.location = x + 100, y - 75
                                    imageNode.image.colorspace_settings.is_data = True
                                    material.node_tree.links.new(occlNode.inputs['Occlusion'], node.outputs['Red'])
                                    material.node_tree.links.new(node.inputs[0], imageNode.outputs['Color'])
                                case 19:
                                    imageNode.label = 'Emissive'
                                    y = -460
                                    material.node_tree.links.new(metlRough.inputs['Emission Color'], imageNode.outputs['Color'])
                                    metlRough.inputs['Emission Strength'].default_value = 1.5
                                case 61:
                                    imageNode.label = 'Alpha Mask'
                                    y = -1380
                                    # Don't make links, MUA3 masks don't look good in Blender
                                case _:
                                    yu -= 460
                                    y = yu
                                    # not 47 (?), 38 (white or checkerboard)
                                    if tex.index != 0:
                                        # 37: channel separated spec?
                                        # https://blenderartists.org/t/how-would-you-use-specular-maps-now-based-on-what-he-said/1225304/
                                        print(f'Unhandled texture type: {tex.textureType} ({tex_name}).')
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
                        # if useAlpha: WIP: Where to get this info?
                        # material.blend_method = 'BLEND'
                        # material.surface_render_method = 'BLEND' else 'DITHERED'
                        obj.data.materials.append(material)
                    # Custom properties can be attached to obj, e.g. obj[MUA3:unknown] = submesh.unknown

                    if not mgdn: collection.objects.link(obj)

                    # WIP: Skeleton as poses
                    # if pose_path:
                    #     import_pose(operator, context, pose_path, limit_bones_to_vertex_groups=True,
                    #             axis_forward=axis_forward, axis_up=axis_up,
                    #             pose_cb_off=pose_cb_off, pose_cb_step=pose_cb_step)
                    #     set_active_object(context, obj)

    for obj in bpy.context.selected_objects: obj.select_set(False)
    for obj in collection.all_objects: obj.select_set(True)
    if scale_objects != 1.0:
        bpy.ops.transform.resize(value=(scale_objects, scale_objects, scale_objects)) # , orient_type='GLOBAL'
    if arm_name in bpy.data.objects:
        ao = bpy.data.objects[arm_name]
        ao.select_set(True)
        context.view_layer.objects.active = ao
        bpy.ops.object.parent_set(type='ARMATURE')


def check_for_4D(mesh, size: int, a: G1MGVertexAttribute, buf: np.ndarray):
    """Checks if the buffer has 4 dimensions and saves the 4th one to vertex attributes."""
    if size == 4 and any(buf[:,3] != 1.0):
        bufc_to_va(mesh, a, buf[:,3], '.w')

def buffer_to_va(mesh, a: G1MGVertexAttribute, buf: np.ndarray, suffix: str = ''):
    """Saves a vertex buffer to vertex attributes."""
    for c, b in enumerate(buf.T):
        bufc_to_va(mesh, a, b, f'.{"xyzwvutsrq"[c]}')

def bufc_to_va(mesh, a: G1MGVertexAttribute, buf: np.ndarray, suffix: str = ''):
    """Saves a one dimensional vertex buffer component to vertex attributes."""
    if 3 < a.dataType < 10 or a.dataType == 0xFF:
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
    node_group.nodes.new('NodeGroupInput')
    return node_group

def pad_weights(vector: np.ndarray, pad_width: tuple, iaxis: int, kwargs: dict):
    """Numpy pad function, which right pads a weight 2D array to normalize the sum to 1.0, if less."""
    if iaxis == 1:
        vector[-pad_width[1]:] = np.clip((1.0 - sum(vector)) / pad_width[1], 0.0, 1.0)
