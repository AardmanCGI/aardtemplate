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
import maya.cmds as cmds # @UnresolvedImport
import maya.mel as mel # @UnresolvedImport
import pymel.core as pm # @UnresolvedImport

import tank # @UnresolvedImport
from tank import Hook # @UnresolvedImport
from tank import TankError # @UnresolvedImport

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

            # publish geo_cache output
            if output["name"] == "geo_cache":
                try:
                   self._publish_geocache_for_item(item, output, work_template, primary_publish_path,
                                                        sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item!")

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})

            progress_cb(100)

        return results

    def _publish_geocache_for_item(self, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Export a geocache for the specified item and publish it
        to Shotgun.
        """
        group_name = item["name"].strip("|")
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]

        # update fields with the group name:
        fields["grp_name"] = group_name

        # create the publish path by applying the fields
        # with the publish template:
        publish_path = publish_template.apply_fields(fields)

        # build and execute the Alembic export command for this item:
        frame_start = int(cmds.playbackOptions(q=True, min=True))
        frame_end = int(cmds.playbackOptions(q=True, max=True))
        # The doCreateGeometryCache command expects forward slashes!
        geo_publish_path = publish_path.replace("\\", "/")

        # Get geometry from cache_SET
        nameSpace = item["name"]
        setName = nameSpace + ':cache_SET'
        tempList = pm.sets(setName, q=True)
        shapes = []
        for each  in tempList:
            shapes.append(each.name())

        shapes.sort()
        pm.select(shapes)

        geo_export_cmd = 'doCreateGeometryCache 6 { "0", "%s", "%s", "OneFile", "0", "%s/%s","1","","0", "export", "0", "1", "1","0","1","mcc","1" } ;'%(frame_start, frame_end, geo_publish_path, nameSpace)
        try:
            self.parent.log_debug("Executing command: %s" % geo_export_cmd)
            pm.mel.eval(geo_export_cmd)
        except Exception, e:
            raise TankError("Failed to export Geometry Cache: %s" % e)

        # Don't think there is any need to register publish of all caches...
        """
        # Finally, register this publish with Shotgun
        self._register_publish(publish_path,
                               group_name,
                               sg_task,
                               publish_version,
                               tank_type,
                               comment,
                               thumbnail_path,
                               [primary_publish_path])
        """

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
