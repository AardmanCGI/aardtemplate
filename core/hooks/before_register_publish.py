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
Hook that gets executed before a publish record is created in Shotgun.
This hook makes it possible to add custom fields to a publish before it gets created
aswell as modifying the content that is being pushed to shotgun.

"""

from tank import Hook
import os
 
class BeforeRegisterPublish(Hook):
    
    def execute(self, shotgun_data, context, **kwargs):
        """
        Gets executed just before a new publish entity is created in Shotgun.
        
        :param shotgun_data: All the data which will be passed to the shotgun create call
        :param context: The context of the publish
        
        :returns: return (potentially) modified data dictionary
        """
        # default implementation is just a pass-through.
        print "before register publish hook"
        
        # get the toolkit api
        import sgtk
        tk = sgtk.sgtk_from_entity(shotgun_data['entity']['type'],shotgun_data['entity']['id'])
        
        path = shotgun_data['path']['local_path']
        print path
        
        # this code should only be run for publish types: GeoCache and Render Sequence
        fields = ['code']
        filters = [['id','is',shotgun_data['published_file_type']['id']]]
        tankTypeObj = tk.shotgun.find_one("PublishedFileType", filters, fields)
        tank_type = tankTypeObj['code']
        
        if tank_type in ['GeoCache', 'Render Sequence']:
            
            # if it's a file we just grab the file name
            if os.path.isfile(path):
                shotgun_data['code'] = os.path.basename(path)
                
            # otherwise we need to create a name
            else:
            
                project = tk.shotgun.find_one("Project", filters=[['id', 'is', shotgun_data['project']['id']]], fields=['tank_name'])
                projname = project['tank_name']
                
                # extract additional fields from the path given
                template = tk.template_from_path(path)
                fields = template.get_fields(path)
                print fields
                
                if 'Shot' in fields:
                    group = fields['Sequence']
                    entity = fields['Shot']
                else:
                    group = fields['sg_asset_type']
                    entity = fields['Asset']
              
                name = fields['name']
                step = fields['Step']
            
                # update the code field, i.e. published file name, with something better than default folder name
                if tank_type == "GeoCache":
                    type = "geocache"
                elif tank_type == "Render Sequence":
                    type = fields["render_type"]
                    
                shotgun_data['code'] = "%s-%s-%s_%s-%s_%s"%(projname,group,entity,name,step,type)
            
        # for some reason shotgun processes paths for publishes that is not sequences in a special way
        # and the easiest way to make this work is to convert all paths to '\\'
        sgPath = path.replace('/', '\\')
        shotgun_data['path']['local_path'] = sgPath
        
        print shotgun_data
        return shotgun_data