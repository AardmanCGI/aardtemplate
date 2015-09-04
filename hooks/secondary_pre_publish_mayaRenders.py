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

class PrePublishHook(Hook):
    """
    Single hook that implements pre-publish functionality
    """
    def execute(self, tasks, work_template, progress_cb, **kwargs):
        """
        Main hook entry point
        :tasks:         List of tasks to be pre-published.  Each task is be a 
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
               
        :progress_cb:   Function
                        A progress callback to log progress during pre-publish.  Call:
                        
                            progress_cb(percentage, msg)
                             
                        to report progress to the UI
                        
        :returns:       A list of any tasks that were found which have problems that
                        need to be reported in the UI.  Each item in the list should
                        be a dictionary containing the following keys:
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
        
        # validate tasks:
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Validating", task)
        
            # depending on output type, do some specific validation:
            if output["name"] == "render":
                # validate that the scene has rendered images to publish:
                errors = self._maya_pre_publish_renders(item, output, work_template, progress_cb)
            else:
                # don't know how to publish other output types!
                errors.append("Don't know how to publish this item!")      

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})
                
            progress_cb(100)
            
        return results


    def _maya_pre_publish_renders(self, item, output, work_template, progress_cb):
        """
        Pre-publish render output
        """
        errors = []
        try:
            # ensure that published files don't already exist
            publish_template = output["publish_template"]        
    
            progress_cb(10.0, "Checking for existing files")
            
            # construct the publish path:
            fields = work_template.get_fields(item["other_params"]["scene_path"])
            publish_path = publish_template.apply_fields(fields)
        
            if os.path.exists(publish_path):
                msg = "Published render files '%s' already exists" % publish_path
                errors.append(msg)
                
        except Exception, e:
            errors.append("Unhandled exception: %s" % e)

        return errors
    
        
       
    
    