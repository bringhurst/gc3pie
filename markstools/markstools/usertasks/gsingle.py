'''
Created on Dec 28, 2009

@author: mmonroe
'''
from optparse import OptionParser
import markstools
import os
import copy
import sys
import numpy as np

from markstools.io.gamess import ReadGamessInp, WriteGamessInp
from markstools.calculators.gamess.calculator import GamessGridCalc
from markstools.lib import utils
from markstools.lib import usertask

from gorg.model.gridtask import TaskInterface
from gorg.lib.utils import Mydb
from gorg.lib import state
from gorg.gridscheduler import STATES as JOB_SCHEDULER_STATES

STATE_WAIT =  state.State.create('WAIT', 'WAIT desc')
STATE_PROCESS =  state.State.create('PROCESS', 'PROCESS desc')
STATE_POSTPROCESS =  state.State.create('POSTPROCESS', 'POSTPROCESS desc')

class GSingle(usertask.UserTask):
 
    STATES = state.StateContainer([STATE_WAIT, STATE_PROCESS, STATE_POSTPROCESS, 
                            usertask.STATE_ERROR, usertask.STATE_COMPLETED])
                            
    def __init__(self):
        self.status = self.STATES.ERROR
        self.status_mapping = {self.STATES.WAIT: self.handle_wait_state, 
                                             self.STATES.PROCESS: self.handle_process_state, 
                                             self.STATES.POSTPROCESS: self.handle_postprocess_state, 
                                             self.STATES.ERROR: self.handle_terminal_state, 
                                             self.STATES.COMPLETED: self.handle_terminal_state}
        self.a_task = None
        self.calculator = None

    def initialize(self, db, calculator, atoms, params, application_to_run='gamess', selected_resource='pra',  cores=2, memory=2, walltime=-1):
        self.calculator = calculator
        self.a_task = TaskInterface(db).create(self.__class__.__name__)
        
        params.title = 'singlejob'
        a_job = self.calculator.generate(atoms, params, self.a_task, application_to_run, selected_resource, cores, memory, walltime)
        self.calculator.calculate(self.a_task)
        markstools.log.info('Submitted task %s for execution.'%(self.a_task.id))
        self.status = self.STATES.WAIT
    
    def handle_wait_state(self):
        from gorg.gridjobscheduler import GridjobScheduler
        job_scheduler = GridjobScheduler('mark','gorg_site','http://130.60.144.211:5984')
        job_list = self.a_task.children
        new_status = self.STATES.PROCESS
        for a_job in job_list:
            job_done = False
            job_scheduler.run()
            job_done = a_job.wait(timeout=0)
            if not job_done:
                new_status=self.STATES.WAIT
                markstools.log.info('Restart waiting for job %s.'%(a_job.id))
                break
        self.status = new_status
    
    def handle_process_state(self):
        job_list = self.a_task.children
        for a_job in job_list:
            a_result = self.calculator.parse(a_job)
            if not a_result.exit_successful():
                a_job.status = JOB_SCHEDULER_STATES.ERROR
                msg = 'GAMESS returned an error while running job %s.'%(a_job.id)
                markstools.log.critical(msg)
                raise Exception, msg
            a_job.status = JOB_SCHEDULER_STATES.COMPLETED
            a_job.store()
        self.status = self.STATES.POSTPROCESS

    def handle_postprocess_state(self):
        self.status = self.STATES.COMPLETED

    def handle_terminal_state(self):
        print 'I do nothing!!'

def main(options):
    # Connect to the database
    db = Mydb('mark',options.db_name,options.db_url).cdb()

    myfile = open(options.file, 'rb')
    reader = ReadGamessInp(myfile)
    myfile.close()
    params = reader.params
    atoms = reader.atoms
    
    gsingle = GSingle()
    gamess_calc = GamessGridCalc(db)
    gsingle.initialize(db, gamess_calc, atoms, params)
    
    gsingle.run()
    import time
    while not gsingle.status.terminal:
        time.sleep(10)
        gsingle.run()

    print 'gsingle done. Create task %s'%(gsingle.a_task.id)
    for a_job in gsingle.a_task.children:
        print 'Job %s has Run %s'%(a_job.id, a_job.run_id)

if __name__ == '__main__':
    #Set up command line options
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-f", "--file", dest="file",default='markstools/examples/water_UHF_gradient.inp', 
                      help="gamess inp to restart from.")
    parser.add_option("-v", "--verbose", action='count', dest="verbose", default=0, 
                      help="add more v's to increase log output.")
    parser.add_option("-n", "--db_name", dest="db_name", default='gorg_site', 
                      help="add more v's to increase log output.")
    parser.add_option("-l", "--db_url", dest="db_url", default='http://130.60.144.211:5984', 
                      help="add more v's to increase log output.")
    (options, args) = parser.parse_args()
    
    import logging
    from markstools.lib.utils import configure_logger
    logging.basicConfig(
        level=logging.ERROR, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
        
    configure_logger(10)
    import gorg.lib.utils
    gorg.lib.utils.configure_logger(10)
    
    main(options)

    sys.exit()
