# Copyright (c) 2024 ak2yny
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html

bl_info = {
    "name": "MUA3 Gust Importer, Exporter",
    "author": "DarkstarSword, eArmada8, Joschuka, ak2yny",
    "version": (0, 0, 3),
    "blender": (4, 1, 0),
    "location": "File > Import-Export",
    "category": "Import-Export",
    "description": "Import and export .g1m 3D objects and associated files from Marvel Ultimate Alliance 3 and other compatible games.",
    "wiki_url": "https://github.com/ak2yny/MUA3_Tools",
    "tracker_url": "https://github.com/ak2yny/MUA3_Tools/issues",
}

import bpy
from .MUA3_Blender_import import MUA3_Gust_Import

def menu_func(self, context):
    self.layout.operator(MUA3_Gust_Import.bl_idname)

def register():
    bpy.utils.register_class(MUA3_Gust_Import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)  # Adds the new operator to an existing menu.

def unregister():
    bpy.utils.unregister_class(MUA3_Gust_Import)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)
