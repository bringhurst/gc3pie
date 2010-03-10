from couchdb import schema as sch
from couchdb.schema import  Schema

from couchdb import client as client
import time

map_func_all = '''
    def mapfun(doc):
        if 'type' in doc:
            if doc['type'] == 'GridjobModel':
                yield None, doc
    '''
map_func_status = '''
    def mapfun(doc):
        if 'type' and 'status' in doc:
            if doc['type'] == 'GridjobModel':
                yield doc['status'], doc
    '''
map_func_author = '''
    def mapfun(doc):
         if 'type' and 'author' in doc:
            if doc['type'] == 'GridjobModel':
                yield doc['author'], doc
    '''
map_func_title = '''
    def mapfun(doc):
        if 'type' and 'title' in doc:
            if doc['type'] == 'GridjobModel':
                yield doc['title'], doc
    '''

class GridjobModel(sch.Document):
    POSSIBLE_STATUS = ('READY', 'WAITING','RUNNING','RETRIEVING','FINISHED', 'DONE','ERROR')
    VIEW_PREFIX = 'gridjob'
    author = sch.TextField()
    title = sch.TextField()
    dat = sch.DateTimeField(default=time.gmtime())
    type = sch.TextField(default='GridjobModel')
    status = sch.TextField(default = 'READY')
    # Type defined by the user
    defined_type = sch.TextField(default='GridjobModel')
    run_params = sch.DictField(default=dict(application_to_run='gamess', selected_resource='ocikbpra',  cores=2, memory=1, walltime=-1))
    # This works like a dictionary, but allows you to go a_job.test.application_to_run='a app' as well as a_job.test['application_to_run']='a app'
    #test=sch.DictField(Schema.build(application_to_run=sch.TextField(default='gamess')))
    gsub_message = sch.TextField()
    file_input = sch.TextField()
    gsub_unique_token = sch.TextField()
#    def __init__(self, author=None, title=None, defined_type=None):
#        super(Gridjobdata, self).__init__()
#        self.author = author
#        self.title = title
#        self.defined_type = defined_type
    
    def __setattr__(self, name, value):
        if name == 'status':
            assert value in self.POSSIBLE_STATUS, 'Invalid status. \
            Only the following are valid, %s'%(' ,'.join(self.POSSIBLE_STATUS))
        super(GridjobModel, self).__setattr__(name, value)
    
    def  put_attachment(self, db, content, filename=None, content_type=None):
        # The doc needs to be in the database before we can attach anything to it
        if not self.id:
            self.store(db)
        result = db.put_attachment(self, content, filename, content_type)
        # After we attach a file we need to update our rev and
        # _attachment field
        return self.load(db, self.id)
        
    def get_attachment(self, db, filename, default=None):
        return db.get_attachment(self, filename, default)
    
    def delete_attachment(self, db, filename):
        return db.delete_attachment(doc, filename)
    
    @classmethod
    def view(cls, db, viewname, **options):
        from couchdb.design import ViewDefinition
        viewnames = cls.sync_views(db, only_names=True)
        assert viewname in viewnames
        a_view = super(cls, cls).view(db, '%s/%s'%(cls.VIEW_PREFIX, viewname), **options)
        #a_view=.view(db, 'all/%s'%viewname, **options)
        return a_view
    
    @classmethod
    def sync_views(cls, db,  only_names=False):
        from couchdb.design import ViewDefinition
        if only_names:
            viewnames=('all', 'by_author', 'by_status', 'by_title')
            return viewnames
        else:
            all = ViewDefinition(cls.VIEW_PREFIX, 'all', map_func_all, wrapper=cls, language='python')
            by_author = ViewDefinition(cls.VIEW_PREFIX, 'by_author', map_func_author, wrapper=cls, language='python')
            by_status = ViewDefinition(cls.VIEW_PREFIX, 'by_status', map_func_status, wrapper=cls,  language='python')
            by_title = ViewDefinition(cls.VIEW_PREFIX, 'by_title', map_func_title, wrapper=cls, language='python')
            views=[all, by_author, by_status, by_title]
            ViewDefinition.sync_many( db,  views)
        return views
    

