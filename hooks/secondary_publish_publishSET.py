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
import maya.mel as mel
import pymel.core

import tank
from tank import Hook
from tank import TankError

from aaCaching import aaPublishedCacheGenerate as aaPCGen
reload(aaPCGen)

import aaSubmit.submitApi
import aaSubmit.utils

class PublishHook(Hook):
    """
    Single hook that implements publish functionality for secondary tasks
    """

    isBaked = False # class variable to only bake camera once

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

        default_thumb = not os.path.exists(thumbnail_path)

        alembic_jobs = []
        alembic_publish_tasks = []

        # publish all tasks:
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []

            # report progress:
            progress_cb(0, "Publishing", task)

            # if there isn't a thumbnail, try to get default one from the config. i've created
            # one for each of our usual publish types.
            if default_thumb:

                # first try for a generic one (ie the primary)
                config_folder = self.parent.tank.pipeline_configuration.get_config_location()
                try:
                    thumbnail_path = self.parent.get_setting("primary_default_thumbnail")
                except Exception, e:
                    print "default thumb fail", str(e)
                else:
                    thumbnail_path = os.path.join(config_folder, thumbnail_path)

                # now try for a more specific one.  this is very ugly, but i couldn't find another
                # way of getting custom attributes from secondary output config..
                try:
                    secondary_config = self.parent.get_setting("secondary_outputs")
                    for c in secondary_config:
                        if c.get('name') == output['name']:
                            thumbnail_path = c.get('default_thumbnail', '')
                            break
                    tp = os.path.join(config_folder, thumbnail_path)
                    if os.path.exists(thumbnail_path):
                        thumbnail_path = tp
                except Exception, e:
                    print "default thumb fail", str(e)
                else:
                    thumbnail_path = os.path.join(config_folder, thumbnail_path)

            # publish alembic_cache output
            if output["name"] == "alembic_cache":
                try:
                   alembic_job, publish_task = self.__publish_alembic_cache(item, output, work_template, primary_publish_path,
                                                sg_task, comment, thumbnail_path, progress_cb)
                   alembic_jobs.append(alembic_job)
                   alembic_publish_tasks.append(publish_task)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)

            # publish obj mesh output
            elif output["name"] == "obj_export":
                try:
                   self.__publish_obj(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)

            # publish anim geocache output
            elif output["name"] == "geocache_export":
                try:
                   self.__publish_geocache(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)

            # publish maya camera output
            elif output["name"] == "mayacamera_export":
                try:
                    print "made it here - publish maya camera output"
                    self.__publish_mayacamera(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)

            # publish alembic camera output
            elif output["name"] == "alembiccamera_export":
                try:
                    print "made it here - publish alembic camera output"
                    self.__publish_alembiccamera(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)
            elif item["type"] == "yeti_node":
                try:
                    self.__publish_yeticache(item, output, work_template, primary_publish_path,
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

        # Submit all alembic jobs to the farm
        # We do it like this so that there's one farm job per publish, not per
        # element to be cached
        if alembic_jobs:
            try:
                scene_path = os.path.abspath(cmds.file(query=True, sn=True))
                scene_file = os.path.basename(scene_path)
                scene_filename = os.path.splitext(scene_file)[0]

                # We need to use str because tractor doesn't accept unicode strings :/
                job = aaSubmit.utils.create_job(str("AC_" + scene_filename), 40)

                args = aaSubmit.submitApi.create_runalembicjobs_args(scene_path, "crate", *alembic_jobs)
                cache_task = aaSubmit.utils.create_task_with_command("Cache", args)

                publish_all_task = aaSubmit.utils.create_task("Publish Alembics", serialSubTasks=False)
                for publish_task in alembic_publish_tasks:
                    aaSubmit.utils.add_subtask(publish_all_task, publish_task)

                serial_task = aaSubmit.utils.create_task("Cache then Publish", serialSubTasks=True)
                aaSubmit.utils.add_subtask(serial_task, cache_task)
                aaSubmit.utils.add_subtask(serial_task, publish_all_task)

                aaSubmit.utils.add_subtask(job, serial_task)
                aaSubmit.utils.submit_job(job)
            except:
                import traceback
                task = next(task for task in tasks if task["output"]["name"] == "alembic_cache")
                results.append({"task": task, "errors": ["Publish failed - " + traceback.format_exc()]})

        return results

    def __publish_alembic_cache(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Publish an Alembic cache file for the scene and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        fields["cache_name"] = item["name"]

        # create the publish path by applying the fields
        # with the publish template:
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)

        # Find additional info from the scene:
        #
        progress_cb(10, "Analysing scene")

        alembic_args = [
                "normals=0",
                "uvs=0",
                "facesets=0",
                "useinitshadgrp=0",
                "dynamictopology=0",
                "transformcache=0",
                "globalspace=0",
                "ogawa=1",
                ]

        # find the animated frame range to use:
        # Don't use self._find_scene_animation_range() because with effects
        # scenes we don't have a anim curve to determine the frame range from
        start_frame = int(cmds.playbackOptions(q=True, min=True))
        end_frame = int(cmds.playbackOptions(q=True, max=True))
        alembic_args.append("in=%d;out=%d" % (start_frame, end_frame))

        # Set the output path:
        # Note: The AbcExport command expects forward slashes!
        alembic_args.append("filename=%s" % publish_path.replace("\\", "/"))

        cache_set = item["name"] + ':cache_SET'
        alembic_args.append("objects=" + ','.join(cmds.sets(cache_set, q=True)))

        job_string = ";".join(alembic_args)

        progress_cb(30, "Preparing publish task for the farm")

        user = tank.util.get_current_user(self.parent.tank)
        args = aaSubmit.submitApi.create_sgpublish_args(
                publish_folder,
                publish_path,
                publish_name,
                publish_version,
                comment or "No comment",
                user["type"],
                user["id"],
                thumbnail_path,
                tank_type,
                sg_task["id"],
                dependencyPaths=[primary_publish_path]
                )
        pub_task = aaSubmit.utils.create_task_with_command(str("Publish " + os.path.basename(publish_path)), args)

        return (job_string, pub_task)


    def __publish_obj(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Export an OBJ geo file for the scene and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # create the publish path by applying the fields
        # with the publish template:
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)

        # Find additional info from the scene:
        #
        progress_cb(20, "Analysing scene")

        # build the export command.
        obj_export_cmd = "file -force -es -pr -typ \"OBJexport\""
        obj_export_cmd += " -options \"groups=1;ptgroups=1;materials=0;smoothing=1;normals=1\""
        obj_export_cmd += " \"%s\"" % (publish_path.replace("\\", "/"))

        # ...and execute it:
        progress_cb(30, "Exporting OBJ file")
        try:
            self.parent.log_debug("Executing command: %s" % obj_export_cmd)

            # make sure plugin is loaded
            if not cmds.pluginInfo('objExport',query=True,loaded=True):
                cmds.loadPlugin('objExport')

            # clear selection, select what's in the set
            sel = cmds.ls(sl=True)
            set_contents = cmds.sets('publish_SET',q=True)
            cmds.select(clear=True)
            for obj in set_contents:
                cmds.select(obj,add=True)

            # do the actual export
            mel.eval(obj_export_cmd)

            # then restore the selection
            cmds.select(clear=True)
            for obj in sel:
                cmds.select(obj,add=True)

        except Exception, e:
            raise TankError("Failed to export OBJ file: %s" % e)

        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": publish_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type":tank_type
        }
        tank.util.register_publish(**args)


    def __publish_geocache(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Publish an Alembic cache file for the scene and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # create the publish path by applying the fields
        # with the publish template:
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)
        # doCreateGeometryCache expects forward slashes
        geo_publish_path = publish_path.replace("\\", "/")

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)

        # Find additional info from the scene:
        #
        progress_cb(10, "Analysing scene")

        # find the animated frame range to use:
        frame_start = int(cmds.playbackOptions(q=True, min=True))
        frame_end = int(cmds.playbackOptions(q=True, max=True))

        namespace = item["name"]
        setName = namespace + ":cache_SET"
        members = pymel.core.sets(setName, q=True)
        transforms = map(lambda m: pymel.core.listRelatives(m, type="transform", allDescendents=True) if not m.endswith("_GEO") else [m], members)
        geos = [geo for geoList in transforms for geo in geoList if geo.endswith("_GEO")]
        pymel.core.select(geos)

        # run the command:
        progress_cb(30, "Exporting GeoCache")

        geo_export_cmd = 'doCreateGeometryCache 6 {{ "0", "{}", "{}", "OneFile", "0", "{}/{}", "1", "", "0", "export", "0", "1", "1", "0", "1", "mcc", "1" }} ;'.format(frame_start, frame_end, geo_publish_path, namespace)
        try:
            # do it
            self.parent.log_debug("Executing command: " + geo_export_cmd)
            mel.eval(geo_export_cmd)
        except Exception, e:
            raise TankError("Failed to export GeoCache: %s" % e)

        # code will be the basename of path (017)
        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": publish_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type":tank_type,
        }
        tank.util.register_publish(**args)


    def __publish_yeticache(self, item, output, work_template, primary_publish_path,
                            sg_task, comment, thumbnail_path, progress_cb):
        """
        Publish an Alembic cache file for the scene and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # the file and folder name is derived from the fur node
        furNodeName = item['name']

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # create the publish path by applying the fields
        # with the publish template:
        publish_template = output["publish_template"]

        # publish path looks something like this at the time of writing
        # C:\mnt\workspace\projects\unPE\spt\tests\furPipeDev\fx\pub\fur\008
        # this is what goes in shotgun, and i'll use it when loading in the
        # results at the other end
        sg_publish_path = publish_template.apply_fields(fields)

        # for performance i think it's best to put each sequence of fur cache
        # files in a subdirectory (we can more quickly get the list of caches
        # from a dir listing that way)
        # the final publish path will look like this
        # # C:\mnt\workspace\projects\unPE\spt\tests\furPipeDev\fx\pub\fur\008\namespace_furNodeShape\namespace_furnodeShape.####.fur
        basename = furNodeName.replace(":","_")
        filename = basename + ".%04d.fur"
        actual_publish_path = os.path.join(sg_publish_path, basename, filename)

        # shotgun publish name will be the rest of the path, past the version
        # eg namespace_furNodeShape/namespace_furnodeShape.####.fur
        #sg_publish_name = "%s/%s" % (basename, filename)

        # determine the publish name (this is kinda the element name master/fur):
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(sg_publish_path)

        # Find additional info from the scene:
        progress_cb(10, "Analysing scene")

        # for the given fur node work out the range to cache. this is the
        # minimum of playback start and the earliest simulation start time for
        # any of the connected grooms
        start_frame = int(cmds.playbackOptions(q=True, min=True))
        end_frame = int(cmds.playbackOptions(q=True, max=True))

        # get the groom nodes. to find an appropriate start frame
        # can't use the yeti command because it doesn't return the namespace of
        # the object
        # groomNodes = cmds.pgYetiCommand(furNodeName, listGrooms=True)
        groomNodes = [n for n in cmds.listConnections(furNodeName, sh=True)
                      if cmds.nodeType(n)=="pgYetiGroom"]
        for groomNode in groomNodes:
            if cmds.getAttr(groomNode+".doSimulation"):
                start_frame = min([start_frame, cmds.getAttr(groomNode+".simStartFrame")])

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(actual_publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # run the command:
        progress_cb(20, "Exporting Yeti Cache")
        self.parent.log_info("Executing command: pgYetiCommand(%s,%s,%s)"\
                               % ( actual_publish_path, start_frame, end_frame ) )
        cmds.pgYetiCommand(furNodeName, writeCache=actual_publish_path,
                           range=(start_frame, end_frame),
                           samples=3,
                           updateViewport=False)

        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": sg_publish_path,
            "name": publish_name, # "fur"
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type":tank_type,
        }
        tank.util.register_publish(**args)


    def __publish_mayacamera(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Export a Maya file for the camera and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # extract entity from camera node name
        # handle full paths, trim off everything after the _
        # e.g. |pivot_GRP|master_CAM -> master
        fields["name"] = item["name"].split("|")[-1].split("_")[0]

        # create the publish path by applying the fields
        # with the publish template:
        fields["Step"] = "cam" # first force step to be camera
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)


        progress_cb(50.0, "Exporting from scene")
        try:
            publish_folder = os.path.dirname(publish_path)
            self.parent.ensure_folder_exists(publish_folder)
            self.parent.log_debug("Exporting to %s..." % (publish_path))

            # stash the selection
            sel = cmds.ls(sl=True)
            # clear it
            cmds.select(clear=True)
            # select just the specific camera we are processing
            cmds.select(item["name"],add=True)

            # do export selection once camera selected
            cmds.file(  publish_path,
                        type='mayaBinary',
                        exportSelected=True,
                        force=True,
                     )

            # reset the selection to what it was prior
            cmds.select(clear=True)
            for obj in sel:
                cmds.select(obj,add=True)

        except Exception, e:
            raise TankError("Failed to export to %s - %s" % (publish_path, e))

        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": publish_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type":tank_type
        }
        tank.util.register_publish(**args)


    def __publish_alembiccamera(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Export an Alembic file for the camera and publish it to Shotgun.

        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # extract entity from camera node name
        # handle full paths, trim off everything after the _
        # e.g. |pivot_GRP|master_CAM -> master
        fields["name"] = item["name"].split("|")[-1].split("_")[0]

        # create the publish path by applying the fields
        # with the publish template:
        fields["Step"] = "cam" # first force step to be camera
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)


        # set up args to export current camera item
        alembic_args = ["-stripNamespaces",
                        "-root %s" % (item["name"]),
                        ]

        # find the animated frame range to use:
        start_frame, end_frame = self._find_scene_animation_range()
        if start_frame and end_frame:
            alembic_args.append("-fr %d %d" % (start_frame, end_frame))

        # Set the output path:
        # Note: The AbcExport command expects forward slashes!
        alembic_args.append("-file %s" % publish_path.replace("\\", "/"))

        # build the export command.  Note, use AbcExport -help in Maya for
        # more detailed Alembic export help
        abc_export_cmd = ("AbcExport -j \"%s\"" % " ".join(alembic_args))

        # ...and execute it:
        progress_cb(30, "Exporting Alembic cache")
        try:
            # make sure plugin is loaded
            if not cmds.pluginInfo('AbcExport',query=True,loaded=True):
                cmds.loadPlugin('AbcExport')
            # do it
            self.parent.log_debug("Executing command: %s" % abc_export_cmd)
            mel.eval(abc_export_cmd)
        except Exception, e:
            raise TankError("Failed to export Alembic Cache: %s" % e)

        except Exception, e:
            raise TankError("Failed to export to %s - %s" % (publish_path, e))

        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": publish_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type":tank_type
        }
        tank.util.register_publish(**args)

    def _find_scene_animation_range(self):
        """
        Find the animation range from the current scene.
        """
        # look for any animation in the scene:
        animation_curves = cmds.ls(typ="animCurve")

        # if there aren't any animation curves then just return
        # a single frame:
        if not animation_curves:
            return (1, 1)

        # something in the scene is animated so return the
        # current timeline.  This could be extended if needed
        # to calculate the frame range of the animated curves.
        start = int(cmds.playbackOptions(q=True, min=True))
        end = int(cmds.playbackOptions(q=True, max=True))

        return (start, end)
