import os
import shelve
import types

from Exceptions import *
import gc3utils
import gc3utils.utils
from InformationContainer import InformationContainer
import Default


# -----------------------------------------------------
# Job
#

# Job is finished on grid or cluster, results have not yet been retrieved.
# User or Application can now call gget.
JOB_STATE_FINISHED = 1

# Job is currently running on a grid or cluster.
# Gc3utils must wait until it finishes to proceed.
JOB_STATE_RUNNING = 2

# Could mean several things:
#   - LRMS failed to accept the job for some reason.
#   - LRMS killed the job.
#   - Job exited with non-zero exit status.
# The User can decide whether to do gget or resubmit or nothing.
JOB_STATE_FAILED = 3

# Job is between the submit phase and confirmed in the LRMS scheduler.
# For example, this applies to ARC jobs after they are submitted but not yet officially queued according to the ARC scheduler.
# SGE+SSH jobs do not have this.
# No action required.
JOB_STATE_SUBMITTED = 4

# Job is finished and results successfully retrieved.
# User or Application can do whatever it wants with the results.
JOB_STATE_COMPLETED = 5

# Job has been deleted with gkill
JOB_STATE_DELETED = 6

# This is the default initial state of a job instance before it has been updated by a gsub/gstat/gget/etc.
# No action required; the state will be set to something else as the code executes.
JOB_STATE_UNKNOWN = 7


#JOB_STATE_HOLD = 7 # Initial state
#JOB_STATE_READY = 8 # Ready for gsub
#JOB_STATE_WAIT = 9 # equivalent to SUBMITTED
#JOB_STATE_OUTPUT = 10 # equivalent to FINISHED
#JOB_STATE_UNREACHABLE = 11 # AuthError
#JOB_STATE_NOTIFIED = 12 # User Notified of AuthError
#JOB_STATE_ERROR = 13 # Equivalent to FAILED


def job_status_to_string(job_status):
    try:
        return {
#            JOB_STATE_HOLD:    'HOLD',
#            JOB_STATE_WAIT:    'WAITING',
#            JOB_STATE_READY:   'READY',
#            JOB_STATE_ERROR:   'ERROR',
            JOB_STATE_FAILED:  'FAILED',
#            JOB_STATE_OUTPUT:  'OUTPUTTING',
            JOB_STATE_RUNNING: 'RUNNING',
            JOB_STATE_FINISHED:'FINISHED',
#            JOB_STATE_NOTIFIED:'NOTIFIED',
            JOB_STATE_SUBMITTED:'SUBMITTED',
            JOB_STATE_COMPLETED:'COMPLETED',
            JOB_STATE_DELETED: 'DELETED'
            }[job_status]
    except KeyError:
        gc3utils.log.error('job status code %s unknown', job_status)
        return 'UNKNOWN'


class Job(InformationContainer):

    def __init__(self,initializer=None,**keywd):
        """
        Create a new Job object.
        
        Examples::
        
        >>> df = Job()
        """
        # create_unique_token
        if ((not keywd.has_key('unique_token')) 
                and not (initializer is not None 
                         and hasattr(initializer, 'has_key') 
                         and initializer.has_key('unique_token'))):
            gc3utils.log.debug('Creating new unique_token ...')
            keywd['unique_token'] = gc3utils.utils.create_unique_token()
            gc3utils.log.debug('... got "%s"' % keywd['unique_token'])
        InformationContainer.__init__(self,initializer,**keywd)

    def is_valid(self):
        if (self.has_key('unique_token')
            #and self.has_key('status') 
            #and self.has_key('resource_name') 
            #and self.has_key('lrms_jobid') 
            ):
            return True


def get_job(unique_token):
    return get_job_filesystem(unique_token)

def get_job_filesystem(unique_token):

    handler = None
    gc3utils.log.debug('retrieving job from %s',Default.JOBS_DIR+'/'+unique_token)

    try:
        if not os.path.exists(Default.JOBS_DIR+'/'+unique_token):
            raise JobRetrieveError('Job not found')
        handler = shelve.open(Default.JOBS_DIR+'/'+unique_token)
        job = Job(handler) 
        handler.close()
        if job.is_valid():
            return job
        else:
            raise JobRetrieveError('Failed retrieving job from filesystem')
    except:
        if handler:
            handler.close()
        raise

def persist_job(job_obj):
    return persist_job_filesystem(job_obj)

def persist_job_filesystem(job_obj):

    handler = None
    gc3utils.log.debug('dumping job in %s',Default.JOBS_DIR+'/'+job_obj.unique_token)
    if not os.path.exists(Default.JOBS_DIR):
        try:
            os.makedirs(Default.JOBS_DIR)
        except Exception, x:
            # raise same exception but add context message
            gc3utils.log.error("Could not create jobs directory '%s': %s" 
                               % (Default.JOBS_DIR, x))
            raise
    try:
        handler = shelve.open(Default.JOBS_DIR+'/'+job_obj.unique_token)
        handler.update(job_obj)
        handler.close()
    except Exception, x:
        gc3utils.log.error("Could not persist job %s to '%s': %s" 
                           % (job_obj.unique_token, Default.JOBS_DIR, x))
        if handler:
            handler.close()
        raise

def clean_job(unique_token):
    return clean_job_filesystem(unique_token)

def clean_job_filesystem(unique_token):
    if os.path.isfile(Default.JOBS_DIR+'/'+unique_token):
        os.remove(Default.JOBS_DIR+'/'+unique_token)
    return 0

def prepare_job_dir(_download_dir):
    try:
        if os.path.isdir(_download_dir):
            # directory exists; move it to .1
            os.rename(_download_dir,_download_dir + "_" + create_unique_token())

        os.makedirs(_download_dir)
        return True

    except:
        gc3utils.log.error('Failed creating folder %s ' % _download_dir)
        gc3utils.log.debug('%s %s',sys.exc_info()[0], sys.exc_info()[1])
        return False
