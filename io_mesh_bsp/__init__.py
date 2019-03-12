#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****

# reload submodules if the addon is reloaded 
if "bpy" in locals():
    import importlib
    importlib.reload(bsp_importer)

# addon information
bl_info = {
    "name": "Import Quake BSP format",
    "author": "Andrew Palmer (with contributions from Ian Cunningham)",
    "version": (0, 0, 95),
    "blender": (2, 80, 0),
    "location": "File > Import > Quake BSP (.bsp)",
    "description": "Import geometry and materials from a Quake 1 BSP file.",
    "wiki_url": "https://github.com/andyp123/blender_io_mesh_bsp",
    "category": "Import-Export",
}

# imports
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.types import Operator
from . import bsp_importer
import time

# main code
class BSPImporter(bpy.types.Operator, ImportHelper):
    bl_idname       = "bsp_importer.bsp"
    bl_description  = "Import geometry from Quake BSP file format (.bsp)"
    bl_label        = "Quake BSP Importer"
    bl_options      = {'UNDO'}

    filename_ext = ".bsp"
    filter_glob: StringProperty(
        default="*.bsp",
        options={'HIDDEN'},
        )

    scale: FloatProperty(
        name="Scale",
        description="Adjust the size of the imported geometry.",
        min=0.0, max=1.0,
        soft_min=0.0, soft_max=1.0,
        default=0.03125, # 1 Meter = 32 Quake units
        )

    create_materials: BoolProperty(
        name="Create materials",
        description="Import textures from the BSP as materials.",
        default=True,
        )

    remove_hidden: BoolProperty(
        name="Remove Hidden",
        description="Remove hidden geometry, such as triggers",
        default=True,
        )

    brightness_adjust: FloatProperty(
        name="Texture Brightness",
        description="Adjust the brightness of imported textures.",
        min=-1.0, max=1.0,
        default=0.0,
        )

    worldspawn_only: BoolProperty(
        name="Worldspawn only",
        description="Import only the main map geometry and ignore other models, such as doors, etc.",
        default=False,
        )

    create_lights: BoolProperty(
        name="Create Lights",
        description="Create light objects in Blender from any light data in the BSP file.",
        default=True,
        )

    create_cameras: BoolProperty(
        name="Create Cameras",
        description="Create Cameras from info_player_start and info_intermission entities.",
        default=True,
        )

    create_entities: BoolProperty(
        name="Create Entities",
        description="Create empties from entity data (monsters, items etc.)",
        default=False,
        )

    all_entities: BoolProperty(
        name="Import All Entities",
        description="Import entity data for invisible entities, such as trigger_relay, info_notnull etc.",
        default=False,
        )
    
    def execute(self, context):
        time_start = time.time()
        options = {
            'scale' : self.scale,
            'create_materials' : self.create_materials,
            'remove_hidden' : self.remove_hidden,
            'brightness_adjust' : self.brightness_adjust,
            'worldspawn_only': self.worldspawn_only,
            'create_lights': self.create_lights,
            'create_cameras': self.create_cameras,
            'create_entities': self.create_entities,
            'all_entities': self.all_entities,
            }
        bsp_importer.import_bsp(context, self.filepath, options)
        print("Elapsed time: %.2fs" % (time.time() - time_start))
        return {'FINISHED'}


classes = (
    BSPImporter,
)

def menu_func(self, context):
    self.layout.operator(BSPImporter.bl_idname, text="Quake BSP (.bsp)")


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.TOPBAR_MT_file_import.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)

    for c in classes:
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
