import sgtk
import os, sys
from PySide.QtCore import *
from PySide.QtGui import *

import nuke

from cgkit import sequence as cgkSeq

# toolkit will automatically resolve the base class for you
# this means that you will derive from the default hook that comes with the app
HookBaseClass = sgtk.get_hook_baseclass()


class SequenceChooser(QDialog):
    '''
    dialog to allow artists to pick sequences from a compound render publish
    '''

    def __init__(self, path, parent=None):
        super(SequenceChooser, self).__init__(parent)
        self.resize(800,350)

        # Create widgets
        self.selector = QListWidget()
        self.selector.setSelectionMode( QAbstractItemView.MultiSelection )
        self.buttons = QDialogButtonBox( QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self )
        # Create layout and add widgets
        layout = QVBoxLayout()
        layout.addWidget(self.selector)
        layout.addWidget(self.buttons)
        # Set dialog layout
        self.setLayout(layout)
        # Connect buttons to close dialog
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # scan folder and add any sequences found
        self.scanDir(path,'')

        # force something to be selected
        if self.selector.count() > 0:
            self.selector.setCurrentRow(0)

    def scanDir(self,rootPath,dir):
        '''
        recursive function to look for sequences in folders
        and add them to the list
        '''
        basePath = os.path.join(rootPath,dir)
        content = os.listdir(basePath)

        # split content into files and folders
        files = []
        folders = []
        for item in content:
            if os.path.isdir(os.path.join(basePath,item)):
                folders.append(item)
            if os.path.isfile(os.path.join(basePath,item)):
                files.append(item)

        # use cgkit to turn the files into file sequence objects
        seqs = cgkSeq.buildSequences(files)

        # loop over combined sequences and folders
        for seq in seqs + folders:
            try:
                # proccess the sequence objects
                name, range = seq.sequenceName()

                # attempt to handle single frame case
                if range == []:
                    range = ['1-1'] #TMP - should this be actual frame number??

                # we must have found a sequence, add it to the list
                item = "%s %s" % (os.path.join(dir,name),range)
                self.selector.addItem(item)
            except:
                # assume that if the sequence processing has failed we must be
                # dealing with a folder
                fullpath = os.path.join(basePath,seq)
                print fullpath
                # recurse if directory, looking for sequences
                if os.path.isdir(fullpath):
                    self.scanDir(rootPath,os.path.join(dir,seq))

    # see what the user selected
    def query(self):
        result = []
        for item in self.selector.selectedItems():
            result.append(item.text())

        return result

    # static method to create the dialog and return
    @staticmethod
    def run(path):
        dialog = SequenceChooser(path)
        result = dialog.exec_()
        value = dialog.query()
        return (value, result == QDialog.Accepted)


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

        if "camera_node" in actions:
            action_instances.append( {"name": "camera_node",
                                      "params": None,
                                      "caption": "Load Alembic Camera",
                                      "description": "This will create a camera node set to read the published alembic camera."} )

        if "render_read_node" in actions:
            action_instances.append( {"name": "render_read_node",
                                      "params": None,
                                      "caption": "Load Render",
                                      "description": "This will allow an individual render layer to be selected from a compound render."} )

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
        path = path.replace('\\','/') #nuke don't like forward slashes

        if name == "camera_node":
            # create camera node in nuke and point it to cache
            nuke.nodes.Camera2(file=path,read_from_file=True)

        if name == "render_read_node":
            # summon the chooser dialog
            selection, ok = SequenceChooser.run(path)
            if ok:
                for value in selection:
                    filePath = value.split(' ')[0]
                    #cgkit uses 1 # as 4 padded - nuke thinks 1 # is 1 digit
                    #cgkit users 1 @ as 1 digit - nuke want's a # for that
                    filePath = filePath.replace('#','%04d')
                    filePath = filePath.replace('@','#')
                    seq = os.path.join( path, filePath )
                    seq = seq.replace('\\','/') #ensure no back slashes in path

                    # get the layer name from the filepath counting from the end
                    tokens = filePath.split('\\')
                    renderLayer = ''
                    if len(tokens) > 1:
                        renderLayer = filePath.split('\\')[-2]


                    # get frame range
                    lowest = 999999;
                    highest = -999999;
                    ## turn the string passed back from the UI into something usable
                    fileRange = value.split(' ')[1]
                    fileRange = fileRange.strip('\'[]')
                    chunks = fileRange.split(',')
                    # frame sequence may not be continuous, so cgk might return 'chunks' of sequences
                    for chunk in chunks:
                        # cgk stores them as a - separated string
                        frames = chunk.split('-')
                        # check the frames to find the start and end
                        for number in frames:
                            number = int(number)
                            if number > highest:
                                highest = number
                            if number < lowest:
                                lowest = number

                    # create the read node in nuke
                    nuke.nodes.Read(file=seq, first=lowest, last=highest, label=renderLayer)

        else:
            # call base class implementation
            super(CustomActions, self).execute_action(name, params, sg_publish_data)
