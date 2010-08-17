import htpie

from htpie.lib import utils
from htpie.lib.exceptions import *
from htpie import model
from htpie import statemachine
from htpie.application import gamess
from htpie.usertasks import gsingle, ghessian

import numpy as np
import glob
import os

_app_tag_mapping = dict()
_app_tag_mapping['gamess']=gamess.GamessApplication

class States(statemachine.States):
    WAITING = u'STATE_WAIT'
    PROCESS = u'STATE_PROCESS'

class Transitions(statemachine.Transitions):
    pass

class GHessianTest(model.Task):

    structure = {'total_jobs': int,
                         'result': [{'fname': unicode,'gsingle': gsingle.GSingle, 'ghessian': ghessian.GHessian,}], 
                        } 
    
    default_values = {
        'state': States.WAITING, 
        '_type':u'GHessianTest', 
        'transition': Transitions.HOLD, 
        'total_jobs':0, 
    }
    
    @classmethod
    def create(cls, dir,  app_tag='gamess', requested_cores=2, requested_memory=2, requested_walltime=2):
        app = _app_tag_mapping[app_tag]
        task = super(GHessianTest, cls,).create()
        task.app_tag = u'%s'%(app_tag)
        
        for a_file in glob.glob('%s/*.inp'%(dir)):
            result = dict()
            
            try:
                dir = utils.generate_temp_dir()
                f_input = open(a_file, 'r')
                f_gamess_hessian = open('%s/gamess_hessian_%s'%(dir, os.path.basename(a_file)), 'w')
                
                atoms, params = app.parse_input(f_input)
                params.set_group_param('$CONTRL', 'RUNTYP', 'HESSIAN')
                app.write_input(f_gamess_hessian, atoms, params)
            finally:
                f_gamess_hessian.close()
                f_input.close()
            
            result['fname'] = u'%s'%(os.path.basename(os.path.basename(f_input.name)))
            result['gsingle'] = gsingle.GSingle.create([f_gamess_hessian.name], app_tag, requested_cores, requested_memory, requested_walltime)
            result['ghessian'] = ghessian.GHessian.create(a_file, app_tag, requested_cores, requested_memory, requested_walltime)
            
            task.result.append(result)
            
        task.transition = Transitions.PAUSED
        task.save()
        return task
    
    def retry(self):
        if self.transition == Transitions.ERROR:
            try:
                self.acquire()
            except:
                raise
            else:
                self.transition = Transitions.PAUSED
                self.release()
            for a_result in self.result:
                a_result['gsingle'].retry()
                a_result['ghessian'].retry()

model.con.register([GHessianTest])

class GHessianTestStateMachine(statemachine.StateMachine):
    _cls_task = GHessianTest
    
    def __init__(self):
        super(GHessianTestStateMachine, self).__init__()
        self.state_mapping.update({States.WAITING: self.handle_waiting_state, 
                                                    States.PROCESS: self.handle_process_state, 
                                                    })

    def handle_waiting_state(self):
        
        count = 0
        for a_result in self.task.result:
            if a_result['ghessian'].transition == Transitions.COMPLETE and \
               a_result['gsingle'].transition == Transitions.COMPLETE:
                count += 1
            elif a_result['ghessian'].transition == Transitions.ERROR or \
                   a_result['gsingle'].transition == Transitions.ERROR:
                raise ChildNodeException('Child node %s errored.'%(a_result['gsingle'].id))
        
        if count == len(self.task.result):
            self.state = States.PROCESS

    def handle_process_state(self):

        self.state = States.COMPLETE
        return True
    
    def handle_kill_state(self):
        children = self.task.children
        for child in children:
            child.acquire()
            child.state = States.KILL
            child.release()
        return True
