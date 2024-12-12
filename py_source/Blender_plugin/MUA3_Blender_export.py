# Based primarily off of:
#   - https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
#   - https://github.com/eArmada8/gust_stuff
#   - https://github.com/Joschuka/Project-G1M and its predecessor https://github.com/Joschuka/fmt_g1m (Python Noesis plugin)
#   - Research of thee GitHub/three-houses-research-team
#   - Research by Yretenai and others
# Many thanks to them, as well as https://github.com/eterniti/g1m_export (& vagonumero13).

# https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html

# import numpy as np
from pathlib import Path
# from struct import unpack_from
import textwrap
# 
# # Project
# from .lib.lib_g1m import G1MGVertexAttribute, G1MHeader, G1MG, G1MG_HEADER_STRUCT, G1MGVAFormat, G1MS # *, G1MM, make_nun_bones, calc_abs_rotation_position, compute_center_of_mass
# from .lib.lib_g1t import g1t_to_dds
# from .lib.lib_gust import *
# from .lib.lib_nun import NUNO, NUNV, NUNS
# from .lib.lib_oid import GLOBAL2OID, OID
# from .MUA3_BIN import get_offsets
# from .MUA3_Formats import GUST_MAGICS
# from .MUA3_G1_Helper import setEndianMagic
# from .MUA3_ZL import un_pack

# Blender
import bpy
from bpy_extras.io_utils import ExportHelper # , axis_conversion, orientation_helper
from bpy.props import BoolProperty, FloatProperty, StringProperty
# from mathutils import Matrix, Quaternion, Vector


# Settings:
MESHES_ADDED, G1MGs, G1MMs, G1MSs, NUNOs, NUNVs, NUNSs, SOFTs = ([] for _ in range(8))
SKELETON_INTERNAL_INDEXP1 = 0


# =================================================================
# Blender export class with options
# =================================================================

class DialogueError(Exception): pass

# @orientation_helper(axis_forward='-Z', axis_up='Y')
class MUA3_Gust_Export(bpy.types.Operator, ExportHelper):
    """Export all meshes and skeletons in the current collection as .g1m 3D objects and associated files for Marvel Ultimate Alliance 3 and other compatible games."""
                                                 # ^^ Use this as a tooltip.
    bl_idname = 'mua3.gust_export'               # Unique identifier.
    bl_label = 'Export Gust Files for MUA3'      # Display name in the interface.
    bl_options = {'PRESET', 'REGISTER', 'UNDO'}  # Enable undo for the operator. WIP: Remove register?

    # For ExportHelper
    filename_ext = '.ZL_' # or .bin, .g1m
    filter_glob: StringProperty(
            default='*.ZL_;*.bin;*.g1m;*.g1t;*.g1a;*.g2a',
            options={'HIDDEN'},
    )

    # Options
    flip_textures_v: BoolProperty(
            name='Flip Textures',
            description='Flip textures vertically during export (ijects referenced images into .g1t files, according to the g1t.json info file).',
            default=False,
    )

    flip_winding: BoolProperty(
            name='Flip Winding Order',
            description="Flip face orientation during export (automatically set to match the import option).",
            default=False,
    )

    flip_normal: BoolProperty(
            name='Flip Normal',
            description="Flip Normals during export (automatically set to match the import option).",
            default=False,
    )

    flip_tangent: BoolProperty(
            name="Flip Tangent",
            description="Flip Tangents during export (automatically set to match the flip normals option).",
            default=False,
            )

    # enable_nun_nodes: BoolProperty(
    #         name='Export NUN Meshes',
    #         description='Export meshes with physique properties. Non functional.',
    #         default=True,
    # )

    # Note: For export, meshes must be imported without merge at this time.

    scale_objects: FloatProperty(
            name = "Scale",
            description = "Scale the objects uniformly, before exporting them.",
            default = 1.0,
            min = 0.0,
            )

    # WIP: Possibly dedicated skeleton path, to be chosen by the user

    def invoke(self, context, event):
        obj = context.object # WIP
        self.flip_winding = obj.get('MUA3:FLIP_WINDING', False)
        self.flip_tangent = self.flip_normal = obj.get('MUA3:FLIP_NORMAL', False)
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        layout = self.layout

        layout.label(text='Select an existing file to merge with.')
        layout.label(text='The file will be backed up during export.')
        layout.separator()

        box = layout.box()
        box.label(text='Flip Options:')
        box.prop(self, 'flip_textures_v')
        box.prop(self, 'flip_winding')
        box.prop(self, 'flip_normal')
        box.prop(self, 'flip_tangent')
        # box = layout.box()
        # box.label(text='Mesh Options:')
        # box.prop(self, 'enable_nun_nodes')
        box = layout.box()
        box.label(text='Transform Options:')
        # box.prop(self, "axis_forward")
        # box.prop(self, "axis_up")
        box.prop(self, "scale_objects")

    def execute(self, context):
        keywords = self.as_keywords(ignore=('filepath',))
        selected_file = Path(self.filepath)
        if selected_file.exists():
            # OID WIP:
            # for oid in (o.name for o in self.files if o.name[-4:].casefold() == '.oid' or o.name[-7:].casefold() == 'oid.bin'):
            #     # get bone ids first
            #     OID((first_file.parent / oid).read_bytes)
            try:
                # Textures need to be read from disk?
                if selected_file.suffix.upper() == '.ZL_':
                    ExportZ(self, context, selected_file, **keywords)
                elif selected_file.suffix.casefold() == '.bin':
                    ExportB(self, context, selected_file, **keywords)
                elif selected_file.suffix.casefold() in ('.g1m', '.g1t', '.g1a', '.g2a'):
                    ExportG(self, context, selected_file.read_bytes(), (0,), selected_file, **keywords)
            except DialogueError as e:
                self.report({'ERROR'}, f"'{selected_file}': \n{e}")
                raise
        else:
            self.report({'ERROR'}, f"'{selected_file}' doesn't exist. Please select an existing file, so the missing information can be imported from it. The selected file is backed up automatically during export.")

        return {'FINISHED'} # Lets Blender know the operator finished successfully.


# =================================================================
# Main Functions
# =================================================================

def ExportZ(op, context, selected_file: Path, **kwargs):
    pass

def ExportB(op, context, selected_file: Path, **kwargs):
    pass

def ExportG(op, context, data: bytes, offsets: tuple, selected_file: Path, **kwargs):
    pass
