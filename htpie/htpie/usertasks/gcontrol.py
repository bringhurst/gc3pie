import htpie

from htpie.lib import utils
from htpie.lib.exceptions import *
from htpie import model
from htpie import statemachine

import sys

module_names = {'GSingle':'htpie.usertasks.gsingle',
                              'GHessian':'htpie.usertasks.ghessian',
                              'GHessianTest':'htpie.usertasks.ghessiantest',
                              'GString':'htpie.usertasks.gstring',
                            }

fsm_classes = dict()
for node_name, node_class in module_names.items():
    __import__(node_class)

class GControl(object):
    
    @staticmethod
    def kill(id):
        doc = model.Task.load(id)
        doc.kill()
        htpie.log.info('Task %s will be killed'%(id))
    
    @staticmethod
    def retry(id):
        doc = model.Task.load(id)
        doc.retry()
        htpie.log.info('Task %s will be retried'%(id))
    
    @staticmethod
    def info(id):
        doc = model.Task.load(id)
        sys.stdout.write('Info on %s %s\n'%(doc['_type'], doc.id))
        sys.stdout.write('Child Ids:\n')
        for child in doc.children:
            sys.stdout.write('%s %s\n'%(child['_type'], child.id))
        
        sys.stdout.write('Input file Containers\n')
        f_list = doc.open('input')
        for f in f_list:
            sys.stdout.write('File: %s\n'%(f.name))
        [f.close() for f in f_list]
        
        f_list = doc.open('output')
        for f in f_list:
            sys.stdout.write('File: %s\n'%(f.name))
        
        if hasattr(doc, 'job'):
            sys.stdout.write('\nGC3 Job: %s\n'%(doc.job))
            sys.stdout.write('\nGC3 Application: %s\n'%(doc.application))
        
        if hasattr(doc, 'neb'):
            print doc
        
        [f.close() for f in f_list]
    
    @staticmethod
    def hessiantest(id):
        self.info(id)
        
        doc = model.Task.load(id)
        for result in doc.result:
            sys.stdout.write('Filename: %s'%(result['fname']))
            sys.stdout.write('Gamess Hessian Run Time')
            sys.stdout.write('Run time: %s\n') 
            #last_exec_d - create_d
            sys.stdout.write('Frequency delta:\n')
            
        for child in doc.children:
            sys.stdout.write('%s %s\n'%(child['_type'], child.id))
        
        sys.stdout.write('Input file Containers\n')
        f_list = doc.open('input')
        for f in f_list:
            sys.stdout.write('File: %s\n'%(f.name))
        [f.close() for f in f_list]
        
        f_list = doc.open('output')
        for f in f_list:
            sys.stdout.write('File: %s\n'%(f.name))
        
        [f.close() for f in f_list]
    
#    def get_task_info(self):
#        sys.stdout.write('Info on Task %s\n'%(self.a_task.id))
#        sys.stdout.write('---------------\n')
#        job_list = self.a_task.children
#        sys.stdout.write('Total number of jobs    %d\n'%(len(job_list)))
#        sys.stdout.write('Overall Task status %s\n'%(self.a_task.status_counts))
#        for a_job in job_list:
#            job_done = False
#            sys.stdout.write('---------------\n')
#            sys.stdout.write('Job %s status %s\n'%(a_job.id, a_job.status))
#            sys.stdout.write('Run %s\n'%(a_job.run_id))
#            sys.stdout.write('gc3utils application obj\n')
#            sys.stdout.write('%s\n'%(a_job.run.application))
#            sys.stdout.write('gc3utils job obj\n')
#            sys.stdout.write('%s\n'%(a_job.run.job))
#            
#            job_done = a_job.wait(timeout=0)
#            if job_done:
#                a_result = self.calculator.parse(a_job)
#                if a_result.exit_successful():
#                    sys.stdout.write('Job exited successfully with energy %s\n'%(a_result.get_potential_energy()))
#                else:
#                    sys.stdout.write('Job did not exit successfully\n')
#
#    def get_task_files(self):
#        job_list = self.a_task.children
#        root_dir = 'tmp'
#        task_dir = '/%s/%s'%(root_dir, self.a_task.id)
#        if not os.path.isdir(task_dir):
#            os.mkdir(task_dir)
#        for a_job in job_list:
#            try:
#                f_list = a_job.attachments
#                sys.stdout.write('Job %s\n'%(a_job.id))
#                for a_file in f_list.values():
#                    shutil.copy2(a_file.name, '%s/%s_%s'%(task_dir, a_job.id, os.path.basename(a_file.name)))
#            finally:
#                map(file.close, f_list.values())
#        sys.stdout.write('Files in directory %s\n'%(task_dir))
