import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to
from gorg_site.lib.base import BaseController, render
from pylons.decorators import jsonify
import os
from gorg_site.model.gridjob import GridjobModel


log = logging.getLogger(__name__)
PERMANENT_STORE = '/home/mmonroe/uploads/'

class GridjobController(BaseController):

    def index(self):
        # Return a rendered template
        #return render('/gridjob.mako')
        # or, return a response
        return 'Hello World'

    @jsonify
    def json_test(self):
        if request.environ['CONTENT_TYPE'] == 'application/json':
            return {'response':'I am json'}
        return render('/submit_job_form.mako')
        
    def submit_form(self):
        return render('/submit_job_form.mako')
    
    def create(self):
        """Post / users: Create a new job in the database."""
        # Myfile is a fieldstorage object provided by pylons
        # myfile.filename = basename of file, myfile.file = file like object
        # myfile.value = contents of file
        myfile = request.POST['myfile'] 
        title = request.POST['title']
        author = request.POST['author']
        user_type='GAMESS'
        new_job=GridjobModel()
        new_job.create(title,  author,  user_type, myfile.filename, myfile.file)
        c.mess = 'Successfully uploaded: %s, title: %s' % \
                (myfile.filename, title)
        return render('/submit_job_finish.mako')
   

