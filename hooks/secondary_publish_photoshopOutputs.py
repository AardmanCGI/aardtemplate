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
import tempfile
import photoshop
import uuid
import re
from itertools import chain

import sgtk
from sgtk import Hook
from sgtk import TankError

class PublishHook(Hook):
    """
    Single hook that implements publish functionality for secondary tasks
    """    
    def execute(self, tasks, work_template, comment, thumbnail_path, sg_task, primary_task, primary_publish_path, progress_cb, **kwargs):
        """
        Main hook entry point
        :param tasks:                   List of secondary tasks to be published.  Each task is a 
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
                        
        :param work_template:           template
                                        This is the template defined in the config that
                                        represents the current work file
               
        :param comment:                 String
                                        The comment provided for the publish
                        
        :param thumbnail:               Path string
                                        The default thumbnail provided for the publish
                        
        :param sg_task:                 Dictionary (shotgun entity description)
                                        The shotgun task to use for the publish    
                        
        :param primary_publish_path:    Path string
                                        This is the path of the primary published file as returned
                                        by the primary publish hook
                        
        :param progress_cb:             Function
                                        A progress callback to log progress during pre-publish.  Call:
                                        
                                            progress_cb(percentage, msg)
                                             
                                        to report progress to the UI
                        
        :param primary_task:            The primary task that was published by the primary publish hook.  Passed
                                        in here for reference.  This is a dictionary in the same format as the
                                        secondary tasks above.
        
        :returns:                       A list of any tasks that had problems that need to be reported 
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
        
        active_doc = photoshop.app.activeDocument
        scene_path = active_doc.fullName.nativePath
        
        # publish all tasks:
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Publishing", task)
            
            # merged doc as tif
            if output["name"] == "tif_output":   
                # publish the layer as a tif:
                output_errors = self.__publish_merged_as_tif(work_template,
                                                            output["publish_template"],
                                                            scene_path,
                                                            active_doc,
                                                            sg_task,
                                                            comment,
                                                            progress_cb)
                if output_errors:
                    errors += output_errors
            # groups        
            elif output["name"] == "export_groups":
                # publish the layer as a tif:
                export_errors = self.__publish_group_as_tif(item["name"], 
                                                            work_template,
                                                            output["publish_template"],
                                                            scene_path,
                                                            active_doc,
                                                            primary_publish_path,
                                                            sg_task,
                                                            comment,
                                                            progress_cb)
                if export_errors:
                    errors += export_errors
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item!") 

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})
             
            progress_cb(100)
             
        return results

    def __publish_merged_as_tif(self, work_template, publish_template, scene_path, active_doc, sg_task, comment, progress_cb):
        """
        Publish the flattened doc as a tif
        """
        errors = []
        progress_cb(10, "Building output path")
        
        # generate the export path using the correct template together
        # with the fields extracted from the work template:
        export_path = None
        
        try:
            fields = work_template.get_fields(scene_path)
            fields = dict(chain(fields.items(), self.parent.context.as_template_fields(publish_template).items()))
            #fields["TankType"] = publish_type
            export_path = publish_template.apply_fields(fields).encode("utf8")
        except TankError, e:
            errors.append("Failed to construct export path: %s" % (e))
            return errors
        
        # ensure the export folder exists:
        export_folder = os.path.dirname(export_path)
        self.parent.ensure_folder_exists(export_folder)
        
        # set unit system to pixels:
        original_ruler_units = photoshop.app.preferences.rulerUnits
        pixel_units = photoshop.StaticObject('com.adobe.photoshop.Units', 'PIXELS')
        photoshop.app.preferences.rulerUnits = pixel_units
        
        try:
            orig_name = active_doc.name
            width_str = active_doc.width
            height_str = active_doc.height
                    
            # set up the export options and get a file object:
            tiff_file = photoshop.RemoteObject('flash.filesystem::File', export_path)
            tiff_save_options = photoshop.RemoteObject('com.adobe.photoshop::TiffSaveOptions')
            tiff_save_options.layers = False
            
            close_save_options = photoshop.flexbase.requestStatic('com.adobe.photoshop.SaveOptions', 'DONOTSAVECHANGES')
            
            progress_cb(20, "Exporting to tif")
            
            # duplicate doc
            doc_name, doc_sfx = os.path.splitext(orig_name)
            temp_doc_name = "%s_temp.%s" % (doc_name, doc_sfx)
            temp_doc = active_doc.duplicate(temp_doc_name)
            try:
                # flatten
                temp_doc.flatten()
                # save:
                temp_doc.saveAs(tiff_file, tiff_save_options, True)
            finally:
                # close the doc:
                temp_doc.close(close_save_options)
            
        finally:
            # set units back to original
            photoshop.app.preferences.rulerUnits = original_ruler_units
            
        return errors
    
    def __publish_group_as_tif(self, group_name, work_template, publish_template, scene_path, active_doc, primary_publish_path, sg_task, comment, progress_cb):
        """
        Publish merged layers in the specified group
        """
        errors = []

        # publish type will be driven from the layer name:
        publish_type = "%s Texture" % group_name.capitalize()

        # generate the export path using the correct template together
        # with the fields extracted from the work template:
        export_path = None
        progress_cb(30, "Building output path")
        
        try:
            fields = work_template.get_fields(scene_path)
            fields = dict(chain(fields.items(), self.parent.context.as_template_fields(publish_template).items()))
            fields["layer"] = group_name        
            export_path = publish_template.apply_fields(fields).encode("utf8")
        except TankError, e:
            errors.append("Failed to construct export path for group '%s': %s" % (group_name, e))
            return errors

        # ensure the export folder exists:
        export_folder = os.path.dirname(export_path)
        self.parent.ensure_folder_exists(export_folder)

        # set unit system to pixels:
        original_ruler_units = photoshop.app.preferences.rulerUnits
        pixel_units = photoshop.StaticObject('com.adobe.photoshop.Units', 'PIXELS')
        photoshop.app.preferences.rulerUnits = pixel_units        

        try:
            orig_name = active_doc.name
            width_str = active_doc.width
            height_str = active_doc.height
            
            # set up the export options and get a file object:
            group_file = photoshop.RemoteObject('flash.filesystem::File', export_path)        
            tiff_save_options = photoshop.RemoteObject('com.adobe.photoshop::TiffSaveOptions')
            tiff_save_options.layers = False
            # trying to get transcparency, but non of the below seems to be working... 
            #tiff_save_options.transparency = True
            #tiff_save_options.alphaChannels = True
            
            close_save_options = photoshop.flexbase.requestStatic('com.adobe.photoshop.SaveOptions', 'DONOTSAVECHANGES')           
            
            progress_cb(40, "Exporting %s group" % group_name)
            
            # duplicate doc
            doc_name, doc_sfx = os.path.splitext(orig_name)
            group_doc_name = "%s_%s.%s" % (doc_name, group_name, doc_sfx)            
            group_doc = active_doc.duplicate(group_doc_name)
            try:
                # set all layers outside of groups visibility to false
                layers = group_doc.artLayers
                for layer in [layers.index(li) for li in xrange(layers.length)]:
                    layer.visible = False
                # set layer visibility
                groups = group_doc.layerSets
                for group in [groups.index(li) for li in xrange(groups.length)]:
                    group.visible = (group.name == group_name)
                # flatten
                group_doc.flatten()
                # save:
                group_doc.saveAs(group_file, tiff_save_options, True)
            finally:
                # close the doc:
                group_doc.close(close_save_options)
                
        finally:
            # set units back to original
            photoshop.app.preferences.rulerUnits = original_ruler_units

        return errors
