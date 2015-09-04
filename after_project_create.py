# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
The after_project_create file is executed as part of creating a new project.
If your starter config needs to create any data in shotgun or do any other
special configuration, you can add it to this file.

The create() method will be executed as part of the setup and is passed
the following keyword arguments:

* sg -         A shotgun connection
* project_id - The shotgun project id that is being setup
* log -        A logger instance to which progress can be reported via
               standard logger methods (info, warning, error etc)

"""
import os
from tank.errors import TankError

def create(sg, project_id, log, **kwargs):
    """
    Insert post-project code here - the default config does not require any post-session stuff.
    """
    # (AD, Shotgun) due to a bug in tk-core v0.15.x, when setting up a project
    # from desktop, create folders will fail as Toolkit thinks it's running from
    # the site config and refuses to create folders for a context based in the
    # new project config.
    #
    # A temporary workaround for this is to clear the 'TANK_CURRENT_PC' env var
    # before creating folders and restoring it afterwards.  This will be fixed
    # in a future release of Toolkit so the workaround can probably be removed
    # at a later date.  Please contact toolkitsupport@shotgunsoftware.com if you
    # need any advice on this.
    current_pc_env = None
    if "TANK_CURRENT_PC" in os.environ:
        current_pc_env = os.environ["TANK_CURRENT_PC"]
        del os.environ["TANK_CURRENT_PC"]
    try:
        _create(sg, project_id, log, **kwargs)
    finally:
        if current_pc_env is not None:
            # reset to the previous value
            os.environ["TANK_CURRENT_PC"] = current_pc_env
        elif "TANK_CURRENT_PC" in os.environ:
            # previous value wasn't set so clear
            del os.environ["TANK_CURRENT_PC"]

def _create(sg, project_id, log, **kwargs):
    """
    Insert post-project code here - the default config does not require any post-session stuff.
    """
    # create a folder structure for the project
    import sgtk
    tk = None
    try:
        tk = sgtk.sgtk_from_entity("Project", project_id)
        if tk:
            tk.create_filesystem_structure("Project", project_id)
            log.info("Created folder structure for the project")
        else:
            log.error("Could not create folder structure for the project")
    except TankError as e:
        log.error("Error creating folders for project: %s" % e)

    # query shotgun database for any shots or assets already created
    # create file structure for each entity
    if sg and tk:
        entities = []
        assets = find_assets_or_spots(sg, project_id, "Assets")
        entities.extend(assets)
        spots = find_assets_or_spots(sg, project_id, "Spots")
        for spot in spots:
            shots = find_shots(sg, project_id,spot["id"])
            entities.extend(shots)
        for entity in entities:
            print entity['type'], entity['code'], entity['id']
            try:
                tk.create_filesystem_structure(entity['type'], entity['id'])
                log.info("Created folders for %s %s %s" % (str(entity['type']), str(entity['code']), str(entity['id'])))
            except TankError as e:
                log.error("Error creating folders for %s %s %s - %s" % (str(entity['type']), str(entity['code']), str(entity['id']), e))


def find_assets_or_spots(sg, project_id, type):
    searchType = "Asset" if type == "Assets" else "Sequence"
    filters = [['project', 'is', {'type':'Project', 'id':project_id}]]
    fields=['id', 'code']
    return sg.find(searchType, filters, fields)

def find_shots(sg, project_id, spotId):
    filters = [['project', 'is', {'type':'Project', 'id':project_id}], ['sg_sequence', 'is', {'type':'Sequence', 'id':spotId}]]
    fields = ['id', 'code']
    return sg.find("Shot", filters, fields)
