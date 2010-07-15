#! /usr/bin/env python
#
"""
Front-end script for submitting ROSETTA jobs to SMSCG.
"""
__docformat__ = 'reStructuredText'
__author__ = 'Riccardo Murri <riccardo.murri@uzh.ch>'
#
# ChangeLog:
#   2010-07-14:
#     * Default session file is now './grosetta.csv', so it's not hidden to users.
#

import sys
import os
import os.path
from optparse import OptionParser
import logging
import csv
import time

import gc3utils
import gc3utils.Default
import gc3utils.gcli
from gc3utils.Job import Job as Gc3utilsJob
import gc3utils.utils


## interface to Gc3Utils

from gc3utils.Application import RosettaDockingApplication

## job control

class Job(Gc3utilsJob):
    """
    A small extension to `gc3utils.Job.Job`, with a few convenience
    extensions.
    """
    def __init__(self, **kw):
        kw.setdefault('log', list())
        kw.setdefault('timestamp', gc3utils.utils.defaultdict(time.time))
        Gc3utilsJob.__init__(self, **kw)
    def is_valid(self):
        # override validity checks -- this will not be a valid `Gc3utilsJob`
        # object until Grid.submit() is called on it ...
        return True

    def set_info(self, msg):
        self.info = msg
        self.log.append(msg)

    def set_state(self, state):
        if state != self.state:
            self.state = state
            epoch = time.time()
            self.timestamp[state] = epoch
            if state == 'NEW':
                self.created = epoch
            self.set_info(state.capitalize() + ' at ' + time.asctime(time.localtime(epoch)))
        

def _get_state_from_gc3utils_job_status(status):
    """
    Convert a gc3utils.Job status code into a readable state description.
    """
    try:
        return {
            1:'FINISHING',
            2:'RUNNING',
            3:'FAILED',
            4:'SUBMITTED',
            5:'DONE',
            6:'DELETED',
            7:'UNKNOWN',
            }[status]
    except KeyError:
        return 'UNKNOWN'

class Grid(object):
    """
    An interface to job lifecycle management.
    """
    def __init__(self, config_file=gc3utils.Default.CONFIG_FILE_LOCATION, default_output_dir=None):
        self.mw = gc3utils.gcli.Gcli(*gc3utils.utils.import_config(config_file))
        self.default_output_dir = default_output_dir

    def save(self, job):
        """
        Save a job using gc3utils' persistence mechanism.
        """
        # update state so that it is correctly saved, but do not use set_state()
        # so the job history is not altered
        job.state = _get_state_from_gc3utils_job_status(job.status)
        job.jobid = job.unique_token # XXX
        gc3utils.Job.persist_job(job)

    def submit(self, application, job=None):
        """
        Submit an instance of the given `application`, and store it
        into `job` (or a new instance of the `Job` class if `job` is
        `None`).  After successful submission, persist job to
        permanent storage.  Return (string) id of submitted job.
        """
        job = self.mw.gsub(application, job)
        return job.unique_token

    def update_state(self, job):
        """
        Update running status of `job`.  In case update fails, state
        is set to 'UNKNOWN'.  Return job state.
        """
        st = self.mw.gstat(job) # `gstat` returns list(!?)
        if len(st) == 0:
            job.set_state('UNKNOWN')
            job.set_info("Could not update job status.")
        else:
            job.set_state(_get_state_from_gc3utils_job_status(job.status))
        return job.state

    def get_output(self, job, output_dir=None):
        """
        Retrieve job's output files into `output_dir`.
        If `output_dir` is `None` (default), then use
        `self.output_dir`. 
        """
        # `job_local_dir` is where gc3utils will retrieve the output
        if output_dir is not None:
            job.job_local_dir = output_dir
        elif self.default_output_dir is not None:
            job.job_local_dir = self.default_output_dir
        else:
            job.job_local_dir = os.getcwd()
        self.mw.gget(job)


    def progress(self, job, can_submit=True, can_retrieve=True):
        """
        Update the job's state and take appropriate action;
        return the (possibly changed) job state.

        If optional argument `can_submit` is `True` (default), will
        try to submit jobs in state ``NEW``.  If optional argument
        `can_retrieve` is `False` (default), will try to fetch job
        results back.
        """
        # update status of SUBMITTED/RUNNING jobs before launching new ones, otherwise
        # we would be checking the status of some jobs twice...
        if job.state == 'SUBMITTED' or job.state == 'RUNNING':
            # update state 
            try:
                self.update_state(job)
            except Exception, x:
                logging.error("Ignoring error in updating state of job '%s.%s': %s: %s"
                              % (job.input, job.instance, x.__class__.__name__, str(x)),
                              exc_info=True)
        if job.state == 'NEW' and can_submit:
            # try to submit; go to 'SUBMITTED' if successful, 'FAILED' if not
            try:
                self.submit(job.application, job)
                job.set_state('SUBMITTED')
            except Exception, x:
                logging.error("Error in submitting job '%s.%s': %s: %s"
                              % (job.input, job.instance, x.__class__.__name__, str(x)))
                sys.excepthook(* sys.exc_info())
                job.set_state('FAILED')
                job.set_info("Submission failed: %s" % str(x))
        if job.state == 'FINISHING' and can_retrieve:
            # get output; go to 'DONE' if successful, 'FAILED' if not
            try:
                # FIXME: temporary fix, should persist `created`!
                if not job.has_key('created'):
                    job.created = time.localtime(time.time())
                self.get_output(job, job.output_dir)
                job.set_state('DONE')
                job.set_info("Results retrieved into directory '%s'" % job.output_dir)
            except Exception, x:
                logging.error("Got error in updating state of job '%s.%s': %s: %s"
                              % (job.input, job.instance, x.__class__.__name__, str(x)), 
                              exc_info=True)
        self.save(job)
        return job.state


class JobCollection(dict):
    """
    A collection of `Job` objects, indexed and accessible by `(input,
    instance)` pair.
    """
    def __init__(self, **kw):
        self.default_job_initializer = kw

    def add(self, job):
        """Add a `Job` instance to the collection."""
        self[job.input, job.instance] = job
    def __iadd__(self, job):
        self.add(job)
        return self

    def remove(self, job):
        """Remove a `Job` instance from the collection."""
        del self[job.input, job.instance]

    def load(self, session):
        """
        Load all jobs from a previously-saved session file.
        The `session` argument can be any file-like object suitable
        for passing to Python's stdlib `csv.DictReader`.
        """
        for row in csv.DictReader(session,  # FIXME: field list must match `job` attributes!
                                  ['input', 'instance', 'jobid', 'state', 'info', 'history']):
            if row['input'].strip() == '':
                # invalid row, skip
                continue 
            id = (row['input'], row['instance'])
            if not self.has_key(id):
                self[id] = Job(unique_token=row['jobid'], ** self.default_job_initializer)
            job = self[id]
            # update state etc.
            job.update(row)
            # resurrect saved state
            job.update(gc3utils.Job.get_job(job.jobid))
            # convert 'history' into a list
            job.log = job.history.split("; ")
            # get back timestamps of various events
            for event in job.log:
                if event.upper().startswith('CREATED'):
                    job.created = time.mktime(time.strptime(event.split(' ',2)[2]))
                if event.upper().startswith('SUBMITTED'):
                    job.timestamp['SUBMITTED'] = time.mktime(time.strptime(event.split(' ',2)[2]))
                if event.upper().startswith('RUNNING'):
                    job.timestamp['RUNNING'] = time.mktime(time.strptime(event.split(' ',2)[2]))
                if event.upper().startswith('FINISHING'):
                    job.timestamp['FINISHING'] = time.mktime(time.strptime(event.split(' ',2)[2]))
                if event.upper().startswith('DONE'):
                    job.timestamp['DONE'] = time.mktime(time.strptime(event.split(' ',2)[2]))

    def save(self, session):
        """
        Save all jobs into a given session file.  The `session`
        argument can be any file-like object suitable for passing to
        Python's standard library `csv.DictWriter`.
        """
        for job in self.values():
            job.history = str.join("; ", job.log)
            csv.DictWriter(session, ['input', 'instance', 'jobid', 'state', 'info', 'history'], 
                           extrasaction='ignore').writerow(job)


## parse command-line

cmdline = OptionParser("grosetta [options] [INPUT ...]",
                       description="""
Compute decoys of specified '.pdb' files by running several
Rosetta 'docking_protocol' instances in parallel.

The `grosetta` command keeps a record of jobs (submitted, executed and
pending) in a session file; at each invocation of the command, the
status of all recorded jobs is updated, output from finished jobs is
collected, and a summary table of all known jobs is printed.

If any INPUT argument is specified on the command line, `grosetta`
appends new jobs to the session file, up to the quantity needed
to compute the requested number of decoys.  Each of the INPUT
parameters can be either a single '.pdb' file, or a directory, which
is recursively scanned for '.pdb' files.

Options can specify a maximum number of jobs that should be in
'SUBMITTED' or 'RUNNING' state; `grosetta` will delay submission
of newly-created jobs so that this limit is never exceeded.
""")
cmdline.add_option("-C", "--continuous", type="int", dest="wait", default=0,
                   metavar="INTERVAL",
                   help="Keep running, monitoring jobs and possibly submitting new ones or"
                   " fetching results every INTERVAL seconds."
                   )
cmdline.add_option("-c", "--cpu-cores", dest="ncores", type="int", default=1, # 1 core
                   metavar="NUM",
                   help="Require the specified number of CPU cores (default: %default)"
                   " for each Rosetta 'docking_protocol' job. NUM must be a whole number."
                   )
cmdline.add_option("-f", "--flags-file", dest="flags_file_path", default=None,
                   metavar="PATH",
                   help="Pass the specified flags file to Rosetta 'docking_protocol'"
                   " Default: '~/.gc3/docking_protocol.flags'"
                   )
cmdline.add_option("-J", "--max-running", type="int", dest="max_running", default=50,
                   metavar="NUM",
                   help="Allow no more than NUM concurrent jobs (default: %default)"
                   " to be in SUBMITTED or RUNNING state."
                   )
cmdline.add_option("-m", "--memory-per-core", dest="memory_per_core", type="int", default=2, # 2 GB
                   metavar="GIGABYTES",
                   help="Require that at least GIGABYTES (a whole number)"
                        " are available to each execution core. (Default: %default)")
cmdline.add_option("-o", "--output", dest="output", default='PATH/',
                   metavar='DIRECTORY',
                   help="Output files from all jobs will be collected in the specified"
                   " DIRECTORY path; by default, output files are placed in the same"
                   " directory where the corresponding input file resides.  If the"
                   " destination directory does not exist, it is created."
                   " Some special strings will be substituted into DIRECTORY,"
                   " to specify an output location that varies with the submitted job:"
                   " NAME is replaced by the input file name (w/out the '.pdb' extension);"
                   " PATH is replaced by the directory where the input file resides;"
                   " INSTANCE is replaced by the sequential no. of the ROSETTA job;"
                   " DATE is replaced by the submission date in ISO format (YYYY-MM-DD);"
                   " TIME is replaced by the submission time formatted as HH:MM."
                   )
cmdline.add_option("-P", "--decoys-per-file", type="int", dest="decoys_per_file", 
                   default=10000,
                   metavar="NUM",
                   help="Compute NUM decoys per input file (default: %default)."
                   )
cmdline.add_option("-p", "--decoys-per-job", type="int", dest="decoys_per_job", 
                   default=15,
                   metavar="NUM",
                   help="Compute NUM decoys in a single job (default: %default)."
                   " This parameter should be tuned so that the running time"
                   " of a single job does not exceed the maximum wall-clock time."
                   )
cmdline.add_option("-s", "--session", dest="session", 
                   default=os.path.join(os.getcwd(), 'grosetta.csv'),
                   metavar="FILE",
                   help="Use FILE to store the status of running jobs (default: '%default')."
                   " Any input files specified on the command line will be added to the existing"
                   " session.  Any jobs already in the session will be monitored and"
                   " their output will be fetched if the jobs are done."
                   )
cmdline.add_option("-v", "--verbose", type="int", dest="verbose", default=0,
                   metavar="LEVEL",
                   help="Increase program verbosity"
                   " (default is 0; any higher number may spoil screen output).",
                   )
cmdline.add_option("-w", "--wall-clock-time", dest="wctime", default=str(8), # 8 hrs
                   metavar="DURATION",
                   help="Each Rosetta job will run for at most DURATION time"
                   " (default: %default hours), after which it"
                   " will be killed and considered failed. DURATION can be a whole"
                   " number, expressing duration in hours, or a string of the form HH:MM,"
                   " specifying that a job can last at most HH hours and MM minutes."
                   )
(options, args) = cmdline.parse_args()

# consistency check
if options.max_running < 1:
    cmdline.error("Argument to option -J/--max-running must be a positive integer.")
if options.decoys_per_file < 1:
    cmdline.error("Argument to option -P/--decoys-per-file must be a positive integer.")
if options.decoys_per_job < 1:
    cmdline.error("Argument to option -p/--decoys-per-job must be a positive integer.")
if options.wait < 0: 
    cmdline.error("Argument to option -C/--continuous must be a positive integer.")

n = options.wctime.count(":")
if 0 == n: # wctime expressed in hours
    duration = int(options.wctime)*60*60
    if duration < 1:
        cmdline.error("Argument to option -w/--wall-clock-time must be a positive integer.")
    options.wctime = duration
elif 1 == n: # wctime expressed as 'HH:MM'
    hrs, mins = str.split(":", options.wctime)
    options.wctime = hrs*60*60 + mins*60
elif 2 == n: # wctime expressed as 'HH:MM:SS'
    hrs, mins, secs = str.split(":", options.wctime)
    options.wctime = hrs*60*60 + mins*60 + secs
else:
    cmdline.error("Argument to option -w/--wall-clock-time must have the form 'HH:MM' or be a duration expressed in seconds.")
# FIXME
options.walltime = int(options.wctime / 3600)

# set verbosity
gc3utils.log.setLevel(max(1, (5-options.verbose)*10))


## build input file list

inputs = []
for path in args:
    if os.path.isdir(path):
        # recursively scan for .pdb files
        for dirpath, dirnames, filenames in os.walk(inputs):
            for filename in filenames:
                if filename.endswith('.pdb'):
                    # like `inputs.append(dirpath + filename)` but make path absolute
                    inputs.append(os.path.realpath(os.path.join(dirpath, filename)))
    elif os.path.exists(path):
        inputs.append(path)
    elif not path.endswith(".pdb") and os.path.exists(path + ".pdb"):
        inputs.append(path + '.pdb')
    else:
        logging.error("Cannot access input path '%s' - ignoring it.", path)

logging.debug("Gathered input file list %s" % inputs)


## compute job list
            
# Application objects are templates for job submission
template = dict()
for input in inputs:
    template[input] = RosettaDockingApplication(
        input, 
        # set computational requirements
        requested_memory = options.memory_per_core,
        requested_cores = options.ncores,
        requested_walltime = options.walltime,
        # Rosetta-specific data
        number_of_decoys_to_create = options.decoys_per_job,
        flags_file_path = options.flags_file_path,
        )

jobs = JobCollection(
    # FIXME: this is a way to ensure `Job` objects have attributes
    # that are not currently persisted!

    # set computational requirements
    requested_memory = options.memory_per_core,
    requested_cores = options.ncores,
    requested_walltime = options.walltime,
    # Rosetta-specific data
    decoys_per_job = options.decoys_per_job,
    flags_file_path = options.flags_file_path,
    )
for input in inputs:
    for nr in range(0, options.decoys_per_file, options.decoys_per_job):
        instance = ("%d--%d" 
                    % (nr, min(options.decoys_per_file, 
                               nr + options.decoys_per_job - 1)))
        jobs += Job(
            input = input,
            instance = instance,
            application = template[input],
            state = 'NEW',
            created = time.time(),
            # set job output directory
            output_dir = (
                options.output
                .replace('NAME', os.path.basename(input))
                .replace('PATH', os.path.dirname(input) or os.getcwd())
                .replace('INSTANCE', instance)
                .replace('DATE', time.strftime('%Y-%m-%d', time.localtime(time.time())))
                .replace('TIME', time.strftime('%H:%M', time.localtime(time.time())))
                ),
            )


## create/retrieve session

try:
    session_file_name = os.path.realpath(options.session)
    if os.path.exists(session_file_name):
        session = file(session_file_name, "r+b")
    else:
        session = file(session_file_name, "w+b")
except IOError, x:
    logging.critical("Cannot open session file '%s' in read/write mode: %s. Aborting."
                     % (options.session, str(x)))
    sys.exit(1)
jobs.load(session)
session.close()


## iterate through job list, updating state and acting accordingly

grid = Grid(default_output_dir=options.output)

def main(jobs):
    # build table
    in_flight_count = 0
    can_submit = True
    can_retrieve = True
    for job in jobs.values():
        state = grid.progress(job, can_submit, can_retrieve)
        if state in [ 'SUBMITTED', 'RUNNING' ]:
            in_flight_count += 1
            if in_flight_count > options.max_running:
                can_submit = False
        if state == 'DONE':
            # nothing more to do - remove from job list if more than 1 day old
            if (time.time() - job.timestamp['DONE']) > 24*60*60:
                jobs.remove(job)
        if job.state == 'FAILED':
            # what should we do?
            # just keep the job around for a while and then remove it?
            if (time.time() - job.timestamp['FAILED']) > 3*24*60*60:
                jobs.remove(job)
    # write updated jobs to session file
    try:
        session = file(session_file_name, "wb")
        jobs.save(session)
        session.close()
    except IOError, x:
        logging.error("Cannot save job status to session file '%s': %s"
                      % (session_file_name, str(x)))
    # print results to user
    if len(jobs) == 0:
        print ("There are no jobs in session file '%s'." % options.session)
    else:
        # pretty-print table of jobs
        print ("%-15s  %-15s  %-18s  %-s" % ("Input file name", "Instance count", "State (JobID)", "Info"))
        print (80 * "=")
        for job in jobs.values():
            print ("%-15s  %-15s  %-18s  %-s" % 
                   (job.input, job.instance, ('%s (%s)' % (job.state, job.jobid)), job.info))


main(jobs)
if options.wait > 0:
    try:
        while True:
            time.sleep(options.wait)
            main(jobs)
    except KeyboardInterrupt: # gracefully intercept Ctrl+C
        pass

sys.exit(0)
