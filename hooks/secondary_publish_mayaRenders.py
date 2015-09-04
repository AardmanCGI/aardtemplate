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
import shutil
import maya.cmds as cmds

import tank
from tank import Hook
from tank import TankError

class PublishHook(Hook):
    """
    Single hook that implements publish functionality for secondary tasks
    """    
    def execute(self, tasks, work_template, comment, thumbnail_path, sg_task, primary_publish_path, progress_cb, **kwargs):
        """
        Main hook entry point
        :tasks:         List of secondary tasks to be published.  Each task is a 
                        dictionary containing the following keys:
                        {
                            item:   Dictionary
                                    This is the item returned by the scan hook 
                                    {   
                                        name:           String
                                        description:    String
                                        type:           String
                                        other_params:   Dictionary
                                    }
                                   
                            output: Dictionary
                                    This is the output as defined in the configuration - the 
                                    primary output will always be named 'primary' 
                                    {
                                        name:             String
                                        publish_template: template
                                        tank_type:        String
                                    }
                        }
                        
        :work_template: template
                        This is the template defined in the config that
                        represents the current work file
               
        :comment:       String
                        The comment provided for the publish
                        
        :thumbnail:     Path string
                        The default thumbnail provided for the publish
                        
        :sg_task:       Dictionary (shotgun entity description)
                        The shotgun task to use for the publish    
                        
        :primary_publish_path: Path string
                        This is the path of the primary published file as returned
                        by the primary publish hook
                        
        :progress_cb:   Function
                        A progress callback to log progress during pre-publish.  Call:
                        
                            progress_cb(percentage, msg)
                             
                        to report progress to the UI
        
        :returns:       A list of any tasks that had problems that need to be reported 
                        in the UI.  Each item in the list should be a dictionary containing 
                        the following keys:
                        {
                            task:   Dictionary
                                    This is the task that was passed into the hook and
                                    should not be modified
                                    {
                                        item:...
                                        output:...
                                    }
                                    
                            errors: List
                                    A list of error messages (strings) to report    
                        }
        """
        results = []
        
        # publish all tasks:
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Publishing", task)
        
            # depending on output type, do some specific validation:
            if output["name"] == "render":
                try:
                    self._maya_publish_renders(item, task, output, work_template, primary_publish_path, 
                                                        sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)
            else:
                # don't know how to publish other output types!
                errors.append("Don't know how to publish this item!")      

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})
             
            progress_cb(100)
             
        return results
    
    def _maya_publish_renders(self, item, task, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Move a WIP render to the PUB folder and publish it
        to Shotgun.
        """
        progress_cb(10, "Finding renders")
 
        # get info we need in order to do the publish:
        source_folder = item["other_params"]["source_folder"]
        filename = item["description"]
        source_path = os.path.join(source_folder, filename)
        
        fields = work_template.get_fields(item["other_params"]["scene_path"])
        publish_template = output["publish_template"]                       
        target_folder = publish_template.apply_fields(fields)
        target_path = os.path.join(target_folder, filename)
        
        # publish (copy files):
        progress_cb(25, "Copying files")

        # copy the file or folder
        try:
            self.parent.ensure_folder_exists(target_folder)
            if os.path.isdir(source_path):
                shutil.copytree (source_path, target_path)
            else:
                self.parent.copy_file(source_path, target_folder, task)
        except Exception, e:
            raise TankError("Failed to copy file from %s to %s - %s" % (source_path, target_folder, e))
            
        progress_cb(40, "Publishing to Shotgun")
            
        # get additional publish info
        publish_version = fields["version"]
        tank_type = output["tank_type"]
                
        # register the publish:
        self._register_publish(target_path, 
                               filename, 
                               sg_task, 
                               publish_version, 
                               tank_type,
                               comment,
                               thumbnail_path, 
                               [primary_publish_path])
   

    def _register_publish(self, path, name, sg_task, publish_version, tank_type, comment, thumbnail_path, dependency_paths=None):
        """
        Helper method to register publish using the 
        specified publish info.
        """
        # construct args:
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": path,
            "name": name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": dependency_paths,
            "published_file_type":tank_type,
        }

        # register publish;
        sg_data = tank.util.register_publish(**args)

        return sg_data



        




