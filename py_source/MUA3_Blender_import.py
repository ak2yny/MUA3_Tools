# https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html

bl_info = {
    "name": "MUA3 Gust Importer, Exporter",
    "author": ", ak2yny",
    "version": (0, 0, 1),
    "blender": (2, 80, 0), # depends, need modern Python, etc.
    "location": "File > Import-Export",
    "category": "Import",
}


import bpy
from bpy_extras.io_utils import ImportHelper


# scene = bpy.context.scene

class MUA3_Gust_Import(bpy.types.Operator, ImportHelper):
    """tt"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "mua3.gust_import"               # Unique identifier.
    bl_label = "Import Gust Files from MUA3"     # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}  # Enable undo for the operator.

    # For ImportHelper
    # filename_ext = ".ZL_, .bin, .g1m, .g1a, .g2a"

    # Options for generation of vertices
    all_lod: BoolProperty(
            name = "Import All LOD",
            description = "Import the mesh for each LOD",
            default = False,
            )

    lod: EnumProperty( # needs to be disabled if all_lod is True
            name = "Select LOD",
            description = "Select which LOD to import",
            items = (
                     ('0', "LOD0", "Highest level of detail"),
                     ('1', "LOD1", ""),
                     ('2', "LOD2", ""),
                     ('3', "LOD3", ""),
                     ),
            default = '0',
            )

    def MissingFunction(): # WIP: ?
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Import Options:")
        box.prop(self, 'all_lod')
        box.prop(self, 'lod')

    def execute(self, context):


def Import():
    pass


def menu_func(self, context):
    self.layout.operator(MUA3_Gust_Import.bl_idname)

def register():
    bpy.utils.register_class(MUA3_Gust_Import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)  # Adds the new operator to an existing menu.

def unregister():
    bpy.utils.unregister_class(MUA3_Gust_Import)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()