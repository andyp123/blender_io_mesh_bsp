# Quake 1 BSP Importer for Blender

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=S3GTZ2J938U6Y&lc=GB&item_name=Andrew%20Palmer&currency_code=GBP&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted)

An add-on for [Blender](https://www.blender.org/) that makes it possible to import
Quake BSP files, including textures (which are stored in the BSP) as materials. It
works with Blender 2.80 and there is an older release for the Blender 2.7x series,
which can be downloaded by clicking [here](https://github.com/andyp123/blender_io_mesh_bsp/releases/download/v0.0.7/io_mesh_bsp.zip).

__Note:__ You will need Blender 2.80 Beta (available [here](https://builder.blender.org/download/))
to run this addon. At the time of writing, Blender 2.80 is still in development, and
this addon may stop functioning due to a change in Blender, but I will try and keep it
working.

## Installation
1. Download the script from GitHub by clicking [here](https://github.com/andyp123/blender_io_mesh_bsp/archive/Blender-2.80.zip).
2. In Blender, open Preferences (Edit > Preferences) and switch to the Add-ons section.
3. Select 'Install Add-on from file...' and select the 'io_mesh_bsp.zip' file that you downloaded.
4. Search for the add-on in the list (enter 'bsp' to quickly find it) and enable it.
5. Save the preferences if you would like the script to always be enabled.

## Usage
Once the addon has been installed, you will be able to import Quake bsp files from
File > Import > Quake BSP (.bsp). Selecting this option will open the file browser
and allow you to select a file to load. Before loading the file, you can tweak some
options to change how the BSP will be imported into Blender.

### Scale (default: 0.05)
Changes the size of the imported geometry. The size of a unit in Quake is not the
same as in Blender. 32 units in Quake is approximately 1m in Blender, so setting
scale to 1 will make everything huge.

### Create Materials (default: On)
Enable or Disable the creation of materials and storing of texture data in the .blend
file.

### Remove Hidden (default: On)
There are some objects in a typical Quake BSP, such as triggers, that are hidden in the
game, but included in the BSP. Disable this to import these objects too. Importing
hidden objects can make it hard to see all the details in the BSP.

### Brightness Adjust (default: 0.0)
Adjust the value of this setting to increase or decrease the brightness of imported
textures.

### Worldspawn Only (default: Off)
Worldspawn is the name given to the first model inside a BSP file. It represents the
static level geometry. Subseqent models in the BSP are dynamic, such as doors, platforms
and triggers. Enabling this will only import this first model.

## View Settings
Once a BSP has been imported, you might want to tweak some viewport settings to better
see the geometry. I recommend using the Solid/Workbench display mode and adjusting the
following:

__Color__: Texture
__Backface Culling__: On
__Specular Lighting__: Off

Disabling Overlays is also recommended.