import os
import maya.cmds as cmds

import tank
from tank import Hook
from tank import TankError

import sgtk

from aaCaching import utils
from aaMayaUtils import shotgun as aaSg

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
        name = os.path.basename(scene_path)

        # Get the toolkit API instance from the engine, then get a context
        tk = self.parent.sgtk
        ctx = tk.context_from_path(scene_name)

        # check for publish_SET in scene.
        sets = cmds.ls(type='objectSet')
        if not 'publish_SET' in sets:
            raise TankError("No publish set found in scene.\n" \
                            "Please create an object set named 'publish_SET'" \
                            " and add all objects to be published to the set.")
        else:
            # save a snapshot so we have a point before the publish to
            # go back to if required
            snapshot_app = sgtk.platform.current_engine().apps.get('tk-multi-snapshot')
            if snapshot_app and snapshot_app.can_snapshot():
                snapshot_app.snapshot('Pre-publish',None)


            # create the primary item
            # this will match the primary output 'scene_item_type':
            items.append({"type": "work_file", "name":name })

            # if we are publishing an anim scene, do the extra geo cache
            if ctx.step['name'] in ['animation','block','effects']:
                # check for any cache_SETs referenced into scene. must be in publish_SET
                for obj in cmds.sets('publish_SET',q=True):
                    # look for sets
                    isSet = False
                    if cmds.nodeType(obj) == 'objectSet':
                        isSet = True
                    # find ones named cache_SET
                    isNamed = False
                    if obj.endswith(':cache_SET'):
                        isNamed = True
                    # check they're referenced
                    isReferenced = False
                    if cmds.referenceQuery(obj,isNodeReferenced=True):
                        isReferenced = True

                    if isSet and isNamed and isReferenced:
                        namespace = obj.split(":")[0]
                        items.append({"type": "cache_set", "name": namespace})

            # yeti fur effects cache?
            if ctx.step['name'] == 'effects':

                # are there any yetiCache_SETS ?
                yetiCacheSets = [o for o in cmds.ls(typ="objectSet") if "yetiCache_SET" in o]

                # if there are any, then add any yeti nodes contained in them
                # to the output
                # get all the yetiNodes that are in yetiCache_SETs
                yetiNodes = []
                if yetiCacheSets:
                    for cacheSet in yetiCacheSets:
                        yetiNodes.extend(utils.getYetiNodesFromSet(cacheSet))

                # make sure we don't add the same node twice in case it's in
                # more than one set
                for yetiNode in list(set(yetiNodes)):

                    # type needs to match the scene_item_type in shot_step.yml
                    # name is the name of the output presented to the user.
                    # this is the yeti node name - which allows people to
                    # override which nodes to cache
                    items.append({"type":"yeti_node", "name":yetiNode})

            # if we are publishing a modelling scene, dump out an obj & abc
            if ctx.step['name'] in ['modelling']:
                #do we want this to be a group or something - compulsory?
                items.append({"type": "mesh_list", "name":'publish set contents'})

            # allow publishing of cameras from any step
            for obj in cmds.sets('publish_SET',q=True):
                # get full path for items
                obj = cmds.ls(obj,long=True)[0]

                # look for cameras
                isCamera = False

                shapes = cmds.listRelatives(obj, fullPath=True, shapes=True)
                if shapes != None:
                    for shape in shapes:
                        if cmds.nodeType(shape) == 'camera':
                            isCamera = True

                # check they are named correctly
                isNamed = False
                if obj.endswith('_CAM'):
                    isNamed = True

                # drop out and notify user if they are trying to publish dodgy cameras
                if isCamera and not isNamed:
                    raise TankError("Incorrectly named camera(s) in publish_SET."\
                                    " Must be '*_CAM'")

                if isCamera and isNamed:
                    # all good, add camera to list
                    items.append({"type": "camera", "name":obj})

        return items
