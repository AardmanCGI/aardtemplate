import sgtk
import os

import pymel.core

from aaCaching import aaPublishedCacheConnectDialog as aaPCC
reload(aaPCC)

from aaCaching import aaPublishedYetiConnectDialog
reload(aaPublishedYetiConnectDialog)

# toolkit will automatically resolve the base class for you
# this means that you will derive from the default hook that comes with the app
HookBaseClass = sgtk.get_hook_baseclass()

class CustomActions(HookBaseClass):

    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.

        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.

        The hook should return at least one action for each item passed in via the
        actions parameter.

        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.

        Because you are operating on a particular publish, you may tailor the output
        (caption, tooltip etc) to contain custom information suitable for this publish.

        The ui_area parameter is a string and indicates where the publish is to be shown.
        - If it will be shown in the main browsing area, "main" is passed.
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed.

        Please note that it is perfectly possible to create more than one action "instance" for
        an action! You can for example do scene introspection - if the action passed in
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than
        one object is returned for an action, use the params key to pass additional
        data into the run_action hook.

        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """

        # get the actions from the base class first
        action_instances = super(CustomActions, self).generate_actions(sg_publish_data, actions, ui_area)

        if "load_cache" in actions:
            action_instances.append( {"name": "load_cache",
                                      "params": None,
                                      "caption": "Load GeoCache",
                                      "description": "This will launch the interface to connect published caches to readers in the current scene."} )
        if "load_alembic" in actions:
            action_instances.append( {"name": "load_alembic",
                                      "params": None,
                                      "caption": "Load Alembic Cache",
                                      "description": "Uses all alembics in the publish folder to update the alembic references on the references renderables."} )
        if "load_yeticache" in actions:
            action_instances.append( {"name": "load_yeticache",
                                      "params": None,
                                      "caption": "Load Yeti Fur Cache",
                                      "description": "This will launch the interface to connect published yeti fur caches to for nodes in the current scene."} )

        return action_instances

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.

        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """

        # resolve local path to publish via central method
        path = self.get_publish_path(sg_publish_data)

        if name == "load_cache":
            # summon the dialog to connect up caches to readers
            aaPCC.connectPublishedCache(path)
        elif name == "load_alembic":
            aaPCC.connectPublishedAlembic(path)
        elif name == "load_yeticache":
            aaPublishedYetiConnectDialog.connectPublishedCache(path)
        else:
            # call base class implementation
            super(CustomActions, self).execute_action(name, params, sg_publish_data)
