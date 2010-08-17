import sys
import htpie
from htpie import model
from htpie import statemachine
from htpie.lib import utils


module_names = {'GSingle':'htpie.usertasks.gsingle',
                              'GHessian':'htpie.usertasks.ghessian',
                              'GHessianTest':'htpie.usertasks.ghessiantest'
                            }

fsm_classes = dict()
for node_name, node_class in module_names.items():
    __import__(node_class)
    fsm_classes[node_name] = (eval('sys.modules[node_class].%s'%(node_name)), 
                                                eval('sys.modules[node_class].%sStateMachine'%(node_name)))

class TaskScheduler(object):
    
    def handle_waiting_tasks(self):
        counter = 0
        for node_name, the_classes in fsm_classes.items():
            node_class = the_classes[0]
            fsm_class = the_classes[1]
            fsm = fsm_class()
            task_name = fsm.name.replace('StateMachine', '')
            to_process = node_class.doc().find({'transition':statemachine.Transitions.PAUSED, '_type': task_name})
            htpie.log.debug('%d %s task(s) are going to be processed'%(to_process.count(),  task_name))
            for a_node in to_process:
                counter += 1
                htpie.log.debug('TaskScheduler is processing task %s'%(a_node.id))
                fsm.load(a_node.id)
                fsm.step()
        htpie.log.info('TaskScheduler has processed %s task(s)'%(counter))

    
    def run(self):
        try:
            self.handle_waiting_tasks()
        except:
            htpie.log.critical('%s errored\n%s'%(self.__class__.__name__, utils.format_exception_info()))
