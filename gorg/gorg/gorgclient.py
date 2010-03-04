import os
import sys
from gorg_site.gorg_site.model.gridjob import GridjobModel
from gorg_site.gorg_site.model.gridtask import GridtaskModel
from gorg_site.gorg_site.lib.mydb import Mydb

def main():
    # We add a job to our database lke this
    db=Mydb('gorg_site','http://127.0.0.1:5984').cdb()
    a_job = GridjobModel()
    GridjobModel.sync_views(db)
    GridtaskModel.sync_views(db)
    a_job.author = 'mark'
    a_job.status = 'SUBMITTED'
    a_job.defined_type = 'GAMESS'
    a_view=GridjobModel.view(db, 'all')
    myfile =  open('/home/mmonroe/Desktop/python-crontab-0.9.2.tar.gz', 'rb')
    a_job.put_attachment(db, myfile, 'a zip')
    myfile.close()
    print 'saved small job to db'
    # Now lets add it to a task
    a_task=GridtaskModel()
    a_task.author='mark'
    for i in range(100):
        a_job = GridjobModel()
        a_job.store(db)
        a_task.add_job(a_job)
    a_task.store(db)
    job_list=a_task.get_jobs(db)
    print 'I added a task'
    
if __name__ == "__main__":
    main()

