from tank import Hook
import os
import re

class ProjectName(Hook):

    def execute(self, sg, project_id, **kwargs):
        """
        Gets executed when the setup_project command needs a disk name preview.
        """
        
        # example: create a name based on both the sg_type field and the name field
        sg_data = sg.find_one("Project", [["id", "is", project_id]], ["name"])
       
        return re.sub("\W", "_", sg_data["name"])

