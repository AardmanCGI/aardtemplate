# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import maya.cmds as cmds

import tank
from tank import Hook
from tank import TankError

class ScanSceneHook(Hook):
    """
    Hook to scan scene for items to publish
    """
    
    def execute(self, **kwargs):
        """
        Main hook entry point
        :returns:       A list of any items that were found to be published.  
                        Each item in the list should be a dictionary containing 
                        the following keys:
                        {
                            type:   String
                                    This should match a scene_item_type defined in
                                    one of the outputs in the configuration and is 
                                    used to determine the outputs that should be 
                                    published for the item
                                    
                            name:   String
                                    Name to use for the item in the UI
                            
                            description:    String
                                            Description of the item to use in the UI
                                            
                            selected:       Bool
                                            Initial selected state of item in the UI.  
                                            Items are selected by default.
                                            
                            required:       Bool
                                            Required state of item in the UI.  If True then
                                            item will not be deselectable.  Items are not
                                            required by default.
                                            
                            other_params:   Dictionary
                                            Optional dictionary that will be passed to the
                                            pre-publish and publish hooks
                        }
        """   
                
        items = []
        
        # get the main scene:
        scene_name = cmds.file(query=True, sn=True)
        if not scene_name:
            raise TankError("Please Save your file before Publishing")
        
        scene_path = os.path.abspath(scene_name)
        scene_basename = os.path.basename(scene_path)

        # create the primary item - this will match the primary output 'scene_item_type':            
        items.append({"type": "work_file", "name": scene_basename})
        
        # create the secondary output - add any wip renders found
        self._add_render_files(scene_path, items)
        
        return items
    
    def _add_render_files(self, path, items):
        """
        Adds the wip render files on disk associated with this maya scene
        """
        tk = tank.sgtk_from_path(path)
        template = tk.template_from_path(path)
        ctx = tk.context_from_path(path)
        
        fields = template.get_fields(path)
        version = fields["version"]
        name = fields["name"]
        
        # get the wip render files path
        if ctx.entity["type"] == "Asset":
            type = fields["sg_asset_type"]
            asset = fields["Asset"]
            maya_asset_render = tk.templates["maya_asset_render"]
            wip_renders = tk.paths_from_template(maya_asset_render, {"sg_asset_type": type, "Asset": asset, "name": name, "version": version})
        elif ctx.entity["type"] == "Shot":
            spot = fields["Sequence"]
            shot = fields["Shot"]
            maya_shot_render = tk.templates["maya_shot_render"]
            wip_renders = tk.paths_from_template(maya_shot_render, {"Sequence": spot, "Shot": shot, "name": name, "version": version})
        
        if wip_renders:
            wip_render_path = wip_renders[0]
            render_files = [name for name in os.listdir(wip_render_path)]
            baseFilename = ""
            for filename in render_files:
                newBaseFilename = filename.split('.')[0]
                if baseFilename != newBaseFilename:
                    items.append({"name": newBaseFilename,
                                  "type": "render_file",
                                  "description":filename,
                                  "other_params": {"source_folder": wip_render_path,
                                                   "scene_path": path}})
                   
                baseFilename = newBaseFilename
        
