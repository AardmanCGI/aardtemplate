import sgtk
import os

import maya.cmds as cmds


# toolkit will automatically resolve the base class for you
# this means that you will derive from the default hook that comes with the app
HookBaseClass = sgtk.get_hook_baseclass()


class CustomOperation(HookBaseClass):


    def execute(self, operation, file_path, context, parent_action, file_version, read_only, **kwargs):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        print context, parent_action, operation

        if operation == "current_path":
            # return the current scene path
            return cmds.file(query=True, sceneName=True)
        elif operation == "open":
            print 'operation is %s' % operation
            print 'parent action is %s' % parent_action
            print 'context is %s' % context
            # get info
            usr = context.user['login']
            scn = os.path.dirname(file_path)
            lockfile = os.path.join(scn,'.lock')
            lockusr = None
            # check for presence of any lock files.
            if os.path.isfile(lockfile):
                with open(lockfile,'r') as lck:
                    # get the name of the user with the lock
                    lockusr = lck.readline()

            if lockusr and lockusr != usr:
                # we have found a lock file and it's not mine, so warn
                result = None
                result = cmds.confirmDialog( title='Confirm',
                                             message='%shas this file open.\nDo you want to proceed?' % (lockusr),
                                             button=['Yes','No'],
                                             defaultButton='Yes',
                                             cancelButton='No',
                                             dismissString='No',
                                            )
                if result == 'Yes':
                    # create lockfile to mark this element as in use
                    lck = open(lockfile,'w')
                    lck.write(usr)
                    lck.close()
                    ## do new scene as Maya doesn't like opening
                    ## the scene it currently has open!
                    cmds.file(new=True, force=True)
                    cmds.file(file_path, open=True, force=True)
                else:
                    pass
            else:
                # no lockfile or i have lock, so just do normal open
                ## do new scene as Maya doesn't like opening
                ## the scene it currently has open!
                cmds.file(new=True, force=True)
                cmds.file(file_path, open=True, force=True)
        elif operation == "save":
            # save the current scene:
            cmds.file(save=True)
        elif operation == "save_as":
            # first rename the scene as file_path:
            cmds.file(rename=file_path)

            # Maya can choose the wrong file type so
            # we should set it here explicitely based
            # on the extension
            maya_file_type = None
            if file_path.lower().endswith(".ma"):
                maya_file_type = "mayaAscii"
            elif file_path.lower().endswith(".mb"):
                maya_file_type = "mayaBinary"

            # save the scene:
            if maya_file_type:
                cmds.file(save=True, force=True, type=maya_file_type)
            else:
                cmds.file(save=True, force=True)

        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            while cmds.file(query=True, modified=True):
                # changes have been made to the scene
                res = QtGui.QMessageBox.question(None,
                                                 "Save your scene?",
                                                 "Your scene has unsaved changes. Save before proceeding?",
                                                 QtGui.QMessageBox.Yes|QtGui.QMessageBox.No|QtGui.QMessageBox.Cancel)

                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.No:
                    break
                else:
                    scene_name = cmds.file(query=True, sn=True)
                    if not scene_name:
                        cmds.SaveSceneAs()
                    else:
                        cmds.file(save=True)

            # do new file:
            cmds.file(newFile=True, force=True)
            return True
