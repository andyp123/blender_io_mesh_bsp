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


# Authors
# Andrew Palmer (andyp.123@gmail.com) - Initial Addon (up to 0.0.4, 0.0.7 onward), Blender 2.80 conversion
# Ian Cunningham - (0.0.5) Import Lights, Set up Cycles materials, Various fixes

import bpy, bmesh
import struct
import os
from collections import namedtuple
from math import radians
from random import uniform # used for setting material color


# type definitions
BSPHeader = namedtuple('BSPHeader', 
    ("version,"
    "entities_ofs,  entities_size,"
    "planes_ofs,    planes_size,"
    "miptex_ofs,    miptex_size,"
    "verts_ofs,     verts_size,"
    "visilist_ofs,  visilist_size,"
    "nodes_ofs,     nodes_size,"
    "texinfo_ofs,   texinfo_size,"
    "faces_ofs,     faces_size,"
    "lightmaps_ofs, lightmaps_size,"
    "clipnodes_ofs, clipnodes_size,"
    "leaves_ofs,    leaves_size,"
    "lface_ofs,     lface_size,"
    "edges_ofs,     edges_size,"
    "ledges_ofs,    ledges_size,"
    "models_ofs,    models_size")
    )
fmt_BSPHeader = '<31I'

BSPModel = namedtuple('BSPModel',
    ("bbox_min_x,  bbox_min_y,  bbox_min_z,"
    "bbox_max_x,   bbox_max_y,  bbox_max_z,"
    "origin_x,     origin_y,    origin_z,"
    "node_id0, node_id1, node_id2, node_id3,"
    "numleafs,"
    "face_id,"
    "face_num")
    )
fmt_BSPModel = '<9f7I'

BSPFace = namedtuple('BSPFace',
    ("plane_id,"
    "size,"
    "ledge_id,"
    "ledge_num,"
    "texinfo_id,"
    "lighttype,"
    "lightlevel,"
    "light0, light1,"
    "lightmap")
    )
fmt_BSPFace = '<HHiHHBBBBi'
fmt_BSP2Face = '<IIiIIBBBBi'

BSPVertex = namedtuple('BSPVertex', 'x, y, z')
fmt_BSPVertex = '<fff'

BSPEdge = namedtuple('BSPEdge', 'vertex0, vertex1')
fmt_BSPEdge = '<HH'
fmt_BSP2Edge = '<II'

BSPTexInfo = namedtuple('BSPTexInfo',
    ("s_x,  s_y,    s_z,    s_dist,"
    "t_x,   t_y,    t_z,    t_dist,"
    "texture_id,"
    "animated")
    )
fmt_BSPTexInfo = '<8f2I'

BSPMipTex = namedtuple('BSPMipTex', 'name, width, height, ofs1, ofs2, ofs4, ofs8')
fmt_BSPMipTex = '<16s6I'

# surfaces with these textures will be ignored
ignored_texnames = (
    "clip",
    "trigger",
    "hint",
    "skip",
    "waterskip",
    "lavaskip",
    "slimeskip",
    "hintskip",
)

imported_entity_prefixes = (
    "monster_",
    "item_",
    "weapon_",
)

camera_types = (
    "info_intermission",
    "info_player_start",
)

light_prefix = "light"

# special texture attributes
transparent_prefix = "{"
liquid_prefix = "*"
sky_prefix = "sky"

fullbright_index = 224 # start of fullbright colors in palette
transparent_index = 255 # transparent color

# functions
def print_debug(string):
    debug = False
    if debug:
        print(string)


def is_imported_entity(classname):
    for prefix in imported_entity_prefixes:
        if classname.startswith(prefix):
            return True
    return False


def parse_float_safe(obj, key, default=0):
    try:
        if key in obj:
            f = float(obj[key])
            return f
    except ValueError:
        pass
    return default


def parse_vec3_safe(obj, key, scale=1):
    if key in obj:
        val = obj[key].split(' ')
        if len(val) is 3:
            try:
                vec = [float(i) * scale for i in val]
                return vec
            except ValueError:
                pass

    return [0, 0, 0]


def load_palette(filepath, brightness_adjust):
    with open(filepath, 'rb') as file:
        colors_byte = struct.unpack('<768B', file.read(768))
        colors = [float(c)/255.0 for c in colors_byte]

        # adjust palette brightness
        if brightness_adjust != 0.0:
            colors = [max(0.0, min(c + brightness_adjust, 1.0)) for c in colors]

        return colors


def generate_mask(fg_indices, width, height, black_background=True):
    fg = 1.0 if black_background else 0.0
    bg = 0.0 if black_background else 1.0

    num_pixels = width * height
    mask_pixels = [bg] * (num_pixels * 4)
    for i in fg_indices:
        x = i % width
        y = (height - 1) - int((i - x) / width) # reverse y
        idx = (width * y + x) * 4
        mask_pixels[idx] = fg
        mask_pixels[idx+1] = fg
        mask_pixels[idx+2] = fg
        mask_pixels[idx+3] = 1.0

    return mask_pixels


def load_textures(context, filepath, brightness_adjust, load_miptex=True):
    with open(filepath, 'rb') as file:
        # read file header
        header_data = file.read(struct.calcsize(fmt_BSPHeader))
        header = BSPHeader._make(struct.unpack(fmt_BSPHeader, header_data))

        # get the list of miptex in the miptex lump (basically a simplified .WAD file inside the bsp)
        file.seek(header.miptex_ofs)
        num_miptex = struct.unpack('<i', file.read(4))[0]
        miptex_ofs_list = struct.unpack('<%di' % num_miptex, file.read(4*num_miptex))

        # load the palette colours (will be converted to RGB float format)
        script_path = os.path.dirname(os.path.abspath(__file__)) + "/"
        colors = load_palette(script_path + "palette.lmp", brightness_adjust)

        # return a list of texture information and image data
        # entry format: dict(name, width, height, image)
        texture_data = []

        # load each mip texture
        for miptex_id in range(num_miptex):
            ofs = miptex_ofs_list[miptex_id]
            # get the miptex header
            file.seek(header.miptex_ofs + ofs)
            miptex_data = file.read(struct.calcsize(fmt_BSPMipTex))
            miptex = BSPMipTex._make(struct.unpack(fmt_BSPMipTex, miptex_data))
            miptex_size = miptex.width * miptex.height
            # because some map compilers do not pad strings with 0s, need to handle that
            for i, b in enumerate(miptex.name):
                if b == 0:
                    miptex_name = miptex.name[0:i].decode('ascii')
                    break
            print_debug("[%d] \'%s\' (%dx%d %dbytes)\n" % (miptex_id, miptex_name, miptex.width, miptex.height, miptex_size))

            texture_item = dict(name=miptex_name, width=miptex.width, height=miptex.height,
                image=None, mask=None, is_emissive=False, use_alpha=False)

            # Only save the basic texture information
            if not load_miptex:
                texture_data.append(texture_item)
                continue

            # get the paletized image pixels
            # if the miptex list is corrupted, make an empty texture to keep id's in order
            try:
                file.seek(header.miptex_ofs + ofs + miptex.ofs1)
                pixels_pal = struct.unpack('<%dB' % miptex_size, file.read(miptex_size))
            except:
                texture_data.append(texture_item)
                print_debug("Texture data seek failed for '%s'" % (miptex_name))
                continue

            # convert the paletized pixels into regular rgba pixels
            # note that i is fiddled with in order to reverse Y
            pixels = []
            fullbright = [] # list containing indices of fullbright pixels
            is_transparent = miptex_name.startswith(transparent_prefix)
            is_emissive = (miptex_name.startswith(liquid_prefix) or miptex_name.startswith(sky_prefix))
            create_mask = (is_emissive is False and miptex_name not in ignored_texnames)

            for y in reversed(range(miptex.height)):
                i = miptex.width * y
                for x in range(miptex.width):
                    idx = i + x
                    c = pixels_pal[idx]

                    # masks
                    alpha = 1.0
                    if create_mask:
                        if is_transparent:
                            if c == transparent_index:
                                alpha = 0.0
                            elif c >= fullbright_index:
                                fullbright.append(idx)
                        elif c >= fullbright_index:
                            fullbright.append(idx)

                    c *= 3
                    pixels.append(colors[c])    # red
                    pixels.append(colors[c+1])  # green
                    pixels.append(colors[c+2])  # blue
                    pixels.append(alpha)        # alpha

            # create an image and save it
            image = bpy.data.images.new(miptex_name, width=miptex.width, height=miptex.height)
            image.pixels = pixels
            texture_item['image'] = image
            texture_item['is_emissive'] = is_emissive
            texture_item['use_alpha'] = is_transparent

            # generate masks if required
            num_pixels = miptex.width * miptex.height
            if len(fullbright) > 0:
                texture_item['is_emissive'] = True
                if len(fullbright) < num_pixels: # no mask if all pixels are fullbright
                    mask = bpy.data.images.new(miptex_name + "_emission", width=miptex.width, height=miptex.height)
                    mask.pixels = generate_mask(fullbright, miptex.width, miptex.height, black_background=True)
                    texture_item['mask'] = mask
            texture_data.append(texture_item)

        return texture_data


# load entity data from the entity lump into an array of simple entity objects
# this data can easily be converted to objects in the scene
def get_entity_data(filepath, entities_ofs, entities_size):
    entities = []
    
    with open(filepath, 'rb') as file:
        file.seek(entities_ofs)
        entity_lump = file.read(entities_size)
        try: # cp437 is extended ascii used frequently for map title decoration etc.
            entity_text = entity_lump.decode('cp437')
            del entity_lump
        except:
            return entities
        lines = entity_text.splitlines()
        del entity_text

        i = 0
        num_lines = len(lines)
        start_char = '{'
        end_char = '}'

        while i < num_lines:
            if lines[i].startswith(start_char):
                i += 1
                entity = {}
                while i < num_lines and not lines[i].startswith(end_char):
                    # split '"classname" "info_player_start"' into key and value
                    kv = [s for s in lines[i].split('"') if s != '' and s != ' ']
                    if len(kv) == 2:
                        entity[kv[0]] = kv[1]
                    i += 1
                if 'classname' in entity and 'origin' in entity:
                    entities.append(entity)
            i += 1

    return entities  


def mesh_add(mesh_id):
    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.add(type='MESH', enter_editmode=True)
    obj = bpy.context.object
    obj.name = "bsp_model_%d" % mesh_id
    # obj.show_name = True
    obj_mesh = obj.data
    obj_mesh.name = obj.name + "_mesh"
    return obj


def entity_add(entity, scale):
    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')

    origin = parse_vec3_safe(entity, 'origin', scale)
    angle = [0, 0, 0]
    angle[2] = parse_float_safe(entity, 'angle', 0)

    bpy.ops.object.add(type='EMPTY', location=origin, rotation=angle)

    obj = bpy.context.object
    obj.name = entity['classname']
    obj.show_name = True
    return obj

def light_add(entity, scale):
    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')

    origin = parse_vec3_safe(entity, 'origin', scale)
    angle = [0, 0, 0]
    angle[2] = parse_float_safe(entity, 'angle', 0)

    bpy.ops.object.add(type='LIGHT', location=origin, rotation=angle)
    light = parse_float_safe(entity, 'light', 200)
    light_data = bpy.context.object.data
    light_data.type = 'POINT'
    light_data.use_nodes = True
    light_data.node_tree.nodes['Emission'].inputs['Strength'].default_value = light

    obj = bpy.context.object
    obj.name = entity['classname']
    obj.show_name = True
    return obj


def camera_add(entity, scale):
    if bpy.context.active_object:
        bpy.ops.object.mode_set(mode='OBJECT')

    origin = parse_vec3_safe(entity, 'origin', scale)
    angle = [0, 0, 0]
    if 'mangle' in entity:
        # mangle is pitch, yaw and roll of the camera
        # assume y is forward vector, so roll is y rotation
        mangle = parse_vec3_safe(entity, 'mangle')
        angle[0] = radians(90 - mangle[0]) # pitch
        angle[1] = radians(mangle[2]) # roll
        angle[2] = radians(mangle[1] - 90) # yaw
    else:
        z = parse_float_safe(entity, 'angle', 0)
        angle[0] = radians(90)
        angle[2] = radians(z - 90)

    bpy.ops.object.add(type='CAMERA', location=origin, rotation=angle)
    camera_data = bpy.context.object.data
    camera_data.lens = 18 # corresponds to 90 degree FOV
    camera_data.lens_unit = 'FOV' # show as FOV in UI

    classname = entity['classname']
    obj = bpy.context.object
    obj.name = classname
    obj.show_name = True

    # set active scene camera
    if classname == 'info_player_start':
        bpy.context.scene.camera = obj

    return obj


def create_materials(texture_data, options):
    for texture_entry in texture_data:
        name = texture_entry['name']
        if (options['remove_hidden'] is True and name in ignored_texnames):
            continue

        # create material
        mat = bpy.data.materials.new(name)
        mat.preview_render_type = 'CUBE'
        mat.use_nodes = True
        mat.diffuse_color = [uniform(0.1, 1.0), uniform(0.1, 1.0), uniform(0.1, 1.0), 1.0]

        image = texture_entry['image']
        mask = texture_entry['mask']

        # There are no images for bsp 30 (Half-Life format)
        if image is None:
            continue

        # pack image data in .blend
        image.pack(as_png=True)
        # create texture from image
        texture = bpy.data.textures.new(name, type='IMAGE')
        texture.image = image
        texture.use_alpha = texture_entry['use_alpha']

        # pack mask texture if there is one
        if mask is not None:
            mask.pack(as_png=True)
            mask_texture = bpy.data.textures.new(name + '_emission', type='IMAGE')
            mask_texture.image = mask
            mask_texture.use_alpha = False

        # set up node tree
        node_tree = mat.node_tree
        main_shader = node_tree.nodes['Principled BSDF']
        output_node = node_tree.nodes['Material Output']
        node_tree.nodes.remove(main_shader) # Replace with Diffuse
        if texture_entry['is_emissive'] and mask is None:
            main_shader = node_tree.nodes.new('ShaderNodeEmission')
        else:
            main_shader = node_tree.nodes.new('ShaderNodeBsdfDiffuse')

        image_node = node_tree.nodes.new('ShaderNodeTexImage')
        image_node.image = image
        image_node.interpolation = 'Closest'
        image_node.location = [-256.0, 300.0]
        node_tree.links.new(image_node.outputs['Color'], main_shader.inputs[0])

        # emission mask shader
        if mask is not None:
            mask_node = node_tree.nodes.new('ShaderNodeTexImage')
            mask_node.image = mask
            mask_node.interpolation = 'Closest'
            mask_mix_shader = node_tree.nodes.new('ShaderNodeMixShader')
            mask_emission_shader = node_tree.nodes.new('ShaderNodeEmission')
            node_tree.links.new(image_node.outputs['Color'], mask_emission_shader.inputs[0])
            node_tree.links.new(mask_node.outputs['Color'], mask_mix_shader.inputs[0])
            node_tree.links.new(main_shader.outputs[0], mask_mix_shader.inputs[1])
            node_tree.links.new(mask_emission_shader.outputs[0], mask_mix_shader.inputs[2])
            main_shader = mask_mix_shader

        node_tree.links.new(main_shader.outputs[0], output_node.inputs['Surface'])

        # set up transparent textures
        if texture_entry['use_alpha']:
            mat.blend_method = 'CLIP' # Eevee material setting
            mix_shader = node_tree.nodes.new('ShaderNodeMixShader')
            trans_shader = node_tree.nodes.new('ShaderNodeBsdfTransparent')
            node_tree.links.new(image_node.outputs['Alpha'], mix_shader.inputs[0])
            node_tree.links.new(trans_shader.outputs[0], mix_shader.inputs[1])
            node_tree.links.new(main_shader.outputs[0], mix_shader.inputs[2])
            node_tree.links.new(mix_shader.outputs[0], output_node.inputs['Surface'])


def import_bsp(context, filepath, options):
    # TODO: Clean this up; Perhaps by loading everything into lists to begin with
    header = 0 # scope header variable outside with block
    bsp2 = False
    with open(filepath, 'rb') as file:
        header_data = file.read(struct.calcsize(fmt_BSPHeader))
        header = BSPHeader._make(struct.unpack(fmt_BSPHeader, header_data))

        # TODO:
        # in order to handle bsp2 files, we need to check the version number here
        # and switch to bsp2 format data structures if the file is bsp2.
        bsp2 = (header.version == 844124994) # magic number of 'BSP2' 

        num_models = int(header.models_size / struct.calcsize(fmt_BSPModel))
        num_verts = int(header.verts_size / struct.calcsize(fmt_BSPVertex))
        if bsp2:
            num_faces = int(header.faces_size / struct.calcsize(fmt_BSP2Face))
            num_edges = int(header.edges_size / struct.calcsize(fmt_BSP2Edge))
        else:
            num_faces = int(header.faces_size / struct.calcsize(fmt_BSPFace))
            num_edges = int(header.edges_size / struct.calcsize(fmt_BSPEdge))

        print_debug("-- IMPORTING BSP --")
        print_debug("Source file: %s (%d)" % (filepath, header.version))
        print_debug("bsp contains %d models (faces = %d, edges = %d, verts = %d)" % (num_models, num_faces, num_edges, num_verts))

        # read models, faces, edges and vertices into buffers
        file.seek(header.models_ofs)
        model_data = file.read(header.models_size)
        file.seek(header.faces_ofs)
        face_data = file.read(header.faces_size)
        file.seek(header.edges_ofs) # actual edges
        edge_data = file.read(header.edges_size)
        file.seek(header.texinfo_ofs)
        texinfo_data = file.read(header.texinfo_size)

        # read in the list of edges and store in readable form (flat list of ints)
        file.seek(header.ledges_ofs)
        edge_index_list = struct.unpack('<%di' % int(header.ledges_size/4), file.read(header.ledges_size))
        # do the same with vertices (flat list of floats)
        file.seek(header.verts_ofs)
        vertex_list = struct.unpack('<%df' % int(header.verts_size/4), file.read(header.verts_size))

    # TODO: Gracefully handle case of no image data contained in bsp (e.g. bsp 30)
    # load texture data (name, width, height, image)
    print_debug("-- LOADING TEXTURES --")
    texture_data = load_textures(context, filepath, options['brightness_adjust'], (header.version is not 30))
    if options['create_materials']:
        create_materials(texture_data, options)

    # create some structs for storing data
    if bsp2:
        face_size = struct.calcsize(fmt_BSP2Face)
        face_struct = struct.Struct(fmt_BSP2Face)
        edge_size = struct.calcsize(fmt_BSP2Edge)
        edge_struct = struct.Struct(fmt_BSP2Edge)
    else:
        face_size = struct.calcsize(fmt_BSPFace)
        face_struct = struct.Struct(fmt_BSPFace)
        edge_size = struct.calcsize(fmt_BSPEdge)
        edge_struct = struct.Struct(fmt_BSPEdge)
    model_size = struct.calcsize(fmt_BSPModel)
    model_struct = struct.Struct(fmt_BSPModel)
    texinfo_size = struct.calcsize(fmt_BSPTexInfo)
    texinfo_struct = struct.Struct(fmt_BSPTexInfo)

    print_debug("-- LOADING MODELS --")
    start_model = 0
    if options['worldspawn_only'] == True:
        end_model = 1
    else:
        end_model = num_models

    added_objects = []
    remove_hidden = options['remove_hidden']
    
    for m in range(start_model, end_model):
        model_ofs = m * model_size
        model = BSPModel._make(model_struct.unpack_from(model_data[model_ofs:model_ofs+model_size]))
        # create new mesh
        obj = mesh_add(m)
        added_objects.append(obj)

        scale = options['scale']
        obj.scale.x = scale
        obj.scale.y = scale
        obj.scale.z = scale
        bm = bmesh.from_edit_mesh(obj.data)
        # create all verts in bsp
        meshVerts = []
        usedVerts = {}
        for v in range(0, num_verts):
            dex = v * 3
            usedVerts[v] = False
            meshVerts.append( bm.verts.new( [vertex_list[dex], vertex_list[dex+1], vertex_list[dex+2] ] ) )
        print_debug("[%d] %d faces" % (m, model.face_num))
        duplicateFaces = 0
        for f in range(0, model.face_num):
            face_ofs = (model.face_id + f) * face_size
            face = BSPFace._make(face_struct.unpack_from(face_data[face_ofs:face_ofs+face_size]))
            texinfo_ofs = face.texinfo_id * texinfo_size
            texinfo = BSPTexInfo._make(texinfo_struct.unpack_from(texinfo_data[texinfo_ofs:texinfo_ofs+texinfo_size]))
            texture_specs = texture_data[texinfo.texture_id]
            texture_name = texture_specs['name']
            # skip faces that use ignored textures
            if remove_hidden and texture_name in ignored_texnames:
                continue

            texS = texinfo[0:3]
            texT = texinfo[4:7]

            # populate a list with vertices
            face_vertices = []
            face_uvs = []

            for i in range(0,face.ledge_num):
                edge_index = edge_index_list[face.ledge_id+i]
                # assuming vertex order is 0->1 
                edge_ofs = edge_index * edge_size
                vert_id = 0
                if edge_index < 0:
                    # vertex order is 1->0
                    edge_ofs = -edge_index * edge_size
                    vert_id = 1
                
                edge = BSPEdge._make(edge_struct.unpack_from(edge_data[edge_ofs:edge_ofs+edge_size]))
                vofs = edge[vert_id] 
                face_vertices.append(meshVerts[vofs])
                usedVerts[vofs] = True

            # find or append material for this face
            material_id = -1
            if options['create_materials']:
                try:
                    material_names = [ m.name for m in obj.data.materials ]
                    material_id = material_names.index(texture_name)
                except: #ValueError:
                    obj.data.materials.append(bpy.data.materials[texture_name])
                    material_id = len(obj.data.materials) - 1
            # try to add face to mesh
            # note that there is a little faff to get the face normals in the correct order
            face = 0
            try:
                face = bm.faces.new((face_vertices[i] for i in reversed(range(-len(face_vertices), 0))))
            except:
                duplicateFaces += 1

            # calculate UVs
            if face != 0:
                uv_layer = bm.loops.layers.uv.verify()
                # thanks to eppo on the BlenderArtists forum for this two line fix
                if hasattr(bm.faces, "ensure_lookup_table"):
                    bm.faces.ensure_lookup_table()
                # bm.faces.layers.tex.verify()
                face = bm.faces[-1] # local bmesh face gets deleted by one of the preceding lines
                for loopElement in face.loops:
                    luvLayer = loopElement[uv_layer]
                    luvLayer.uv[0] =  (loopElement.vert.co.dot(texS) + texinfo.s_dist)/texture_specs['width']
                    luvLayer.uv[1] = -(loopElement.vert.co.dot(texT) + texinfo.t_dist)/texture_specs['height']

                # assign material
                if options['create_materials'] and material_id != -1:
                    face.material_index = material_id

        if duplicateFaces > 0:
            print_debug("%d duplicate faces not created in model %d" % (duplicateFaces, m))
    
        # remove unused vertices from this model
        for vi in range(0, num_verts):
            if not usedVerts[vi]:
                bm.verts.remove(meshVerts[vi])
        # update the mesh with data from the bmesh
        bmesh.update_edit_mesh(obj.data)

    bpy.ops.object.mode_set(mode='OBJECT')

    # move objects to a new collection
    bpy.ops.object.select_all(action='DESELECT')
    for obj in added_objects:
        obj.select_set(True)
    map_name = os.path.basename(filepath).split('.')[0]
    bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=map_name)

    # delete mesh objects with no faces
    bpy.ops.object.select_all(action='DESELECT')
    deleted_objects = [obj for obj in added_objects if obj.type == 'MESH' and len(obj.data.polygons) == 0]
    for obj in deleted_objects:
        obj.select_set(True)
    bpy.ops.object.delete()

    # create entities, lights and cameras
    bpy.ops.object.select_all(action='DESELECT')
    create_entities = options['create_entities']
    create_lights = options['create_lights']
    create_cameras = options['create_cameras']
    import_all = options['all_entities']
    if create_entities or create_cameras or create_lights or import_all:
        scale = options['scale']

        entities = get_entity_data(filepath, header.entities_ofs, header.entities_size)
        added_objects = []
        added_lights = []
        for entity in entities:
            classname = entity['classname']
            obj = None
            # this stops lights being imported as empties, even with import_all enabled
            if classname.startswith('light'):
                if create_lights:
                    obj = light_add(entity, scale)
                    added_lights.append(obj)
            elif create_cameras and classname in camera_types:
                obj = camera_add(entity, scale)
                added_objects.append(obj)
            elif import_all is True or (create_entities and is_imported_entity(classname)):
                obj = entity_add(entity, scale)
                added_objects.append(obj)

        if len(added_objects) > 0:
            for obj in added_objects:
                obj.select_set(True)
            bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=map_name + "_entities")
            bpy.ops.object.select_all(action='DESELECT')

        if len(added_lights) > 0:
            for obj in added_lights:
                obj.select_set(True)
            bpy.ops.object.move_to_collection(collection_index=0, is_new=True, new_collection_name=map_name + "_lights")
            bpy.ops.object.select_all(action='DESELECT')

    # set up view
    view_3d_areas = [area for area in bpy.context.screen.areas if area.ui_type == 'VIEW_3D']
    for viewport in view_3d_areas:
        for space in viewport.spaces:
            if hasattr(space, 'shading'):
                shading = space.shading
                shading.type = 'SOLID' # Workbench engine
                shading.light = 'STUDIO' # Studio lights (needed for some of the following options)
                shading.color_type = 'TEXTURE' # textured mode (only available with FLAT and STUDIO lighting)
                shading.show_backface_culling = True
                shading.show_specular_highlight = False

    print_debug("-- IMPORT COMPLETE --")
