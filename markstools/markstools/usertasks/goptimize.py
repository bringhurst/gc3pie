import markstools

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

STATE_WAIT = state.State.create('WAIT', 'WAIT desc')
STATE_STEP = state.State.create('STEP', 'STEP desc')
STATE_POSTPROCESS = state.State.create('POSTPROCESS', 'POSTPROCESS desc')

class GOptimize(usertask.UserTask):
    STATES = state.StateContainer([STATE_WAIT, STATE_STEP, STATE_POSTPROCESS, 
                            usertask.STATE_ERROR, usertask.STATE_COMPLETED])
                            
    def __init__(self):
        self.status = self.STATES.ERROR
        self.status_mapping = {self.STATES.WAIT: self.handle_wait_state, 
                                             self.STATES.STEP: self.handle_step_state, 
                                             self.STATES.ERROR: self.handle_terminal_state, 
                                             self.STATES.COMPLETED: self.handle_terminal_state}
        
        self.a_task = None
        self.calculator = None
        self.optimizer = None

    def initialize(self, db, calculator, optimizer, atoms, params, application_to_run='gamess', selected_resource='gc3',  cores=8, memory=2, walltime=1):
        self.calculator = calculator
        self.a_task = TaskInterface(db).create(self.__class__.__name__)
        self.optimizer = optimizer
        self.optimizer.initialize()
        try:
            myfile = self.optimizer.dump()
            self.a_task.put_attachment(myfile, 'optimizer')
        finally:
            myfile.close()
        params.title = 'a_job'
        a_job = self.calculator.generate(atoms, params, self.a_task, application_to_run, selected_resource, cores, memory, walltime)
        self.calculator.calculate(self.a_task)
        self.status = self.STATES.WAIT
        self.save()
    
    def handle_wait_state(self):
        job_list = [self.a_task.children[-1]]
        new_status = self.STATES.STEP
        for a_job in job_list:
            job_done = False
            job_done = a_job.wait(timeout=0)
            if not job_done:
                new_status=self.STATES.WAIT
                markstools.log.info('Waiting for job %s.'%(a_job.id))
                break
        self.status = new_status
    
    def handle_step_state(self):
        a_job = self.a_task.children[-1]
        a_result = self.calculator.parse(a_job)
        myfile = a_job.get_attachment('.inp')
        reader = ReadGamessInp(myfile)
        myfile.close()
        params = reader.params
        params.title ='a_title'
        atoms = reader.atoms
        try:
            myfile = self.a_task.get_attachment('optimizer')
            self.optimizer.load(myfile)
        finally:
            myfile.close()
        #restart if we need to
        new_positions = self.optimizer.step(a_result.atoms.get_positions(), a_result.get_forces())
        try:
            myfile = self.optimizer.dump()
            self.a_task.put_attachment(myfile, 'optimizer')
        finally:
            myfile.close()
        atoms.set_positions(new_positions)
        new_job = self.calculator.generate(atoms, params, self.a_task, 
                                                                a_job.run.application.application_tag, a_job.run.application.requested_resource,  
                                                                a_job.run.application.requested_cores, a_job.run.application.requested_memory, 
                                                                a_job.run.application.requested_walltime)
        self.calculator.calculate(new_job)
        self.status = self.STATES.WAIT
    
    def handle_terminal_state(self):
        pass
        
    @staticmethod
    def optimizer_list():
        opt_list = ['fire', 'lbfgs']
        return opt_list

    @staticmethod
    def select_optimizer(optimizer_str):
        from markstools.optimize import lbfgs
        from markstools.optimize import fire
        mapping = dict(lbfgs=lbfgs.LBFGS, fire=fire.FIRE)
        optimizer = mapping.get(optimizer_str, None)()
        if optimizer is None:
            raise 'Incorrect OPT', 'Your optimizer selection is not valid'
        return optimizer


