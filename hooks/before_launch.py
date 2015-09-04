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
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import os
import tank  # @UnresolvedImport


class BeforeAppLaunch(tank.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    def execute(self, **kwargs):
        """
        The execute functon of the hook will be called to start the required application
        """

        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_publiish_app = self.parent
        # > current_entity = multi_publiish_app.context.entity

        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        # Get the current context
        context, project, entity, sg, engine = self._get_shotgun_context_info()

        # Get the toolkit API instance from the engine
        tk = engine.sgtk

        # setting env vars for child processes to read
        os.environ["SG_PROJECT_PATH"] = tk.project_path


        # if you are using a shared hook to cover multiple applications,
        # you can use the engine setting to figure out which application
        # is currently being launched:
        #
        # > multi_publiish_app = self.parent
        # > if multi_publiish_app.get_setting("engine") == "tk-nuke":
        #       do_something()

    def _get_shotgun_context_info(self):
        multi_launch_app = self.parent
        context = multi_launch_app.context
        project = context.project
        entity = context.entity
        engine = multi_launch_app.engine
        sg = engine.shotgun
        return context, project, entity, sg, engine
