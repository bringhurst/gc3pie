#!/usr/bin/env python
"""
Implementation of the `gcli` command-line front-ends.
"""
__docformat__='reStructuredText'
__version__ = '$Revision$'

__author__="Sergio Maffioletti <sergio.maffioletti@gc3.uzh.ch>, Riccardo Murri <riccardo.murri@uzh.ch>"
__date__ = '$Date$'
__copyright__="Copyright (c) 2009,2010 Grid Computing Competence Center, University of Zurich"



import sys
import os
import ConfigParser
from optparse import OptionParser
import time

import gc3libs
import gc3libs.application.gamess as gamess
import gc3libs.application.rosetta as rosetta
import gc3libs.Default as Default
from   gc3libs.Exceptions import *
import gc3libs.Job as Job
import gc3libs.gcli as gcli
import gc3libs.utils as utils

import gc3utils


# defaults - XXX: do they belong in ../gcli.py instead?
_homedir = os.path.expandvars('$HOME')
_rcdir = _homedir + "/.gc3"
_default_config_file_locations = [ "/etc/gc3/gc3pie.conf", _rcdir + "/gc3pie.conf" ]
_default_joblist_file = _rcdir + "/.joblist"
_default_joblist_lock = _rcdir + "/.joblist_lock"
_default_job_folder_location = os.getcwd()
_default_wait_time = 3 # XXX: does it really make sense to have a default wall-clock time??


def _configure_logger(verbosity):
    """
    Configure the logger verbosity.
    """
    logging_level = max(1, (5-verbosity)*10)
    gc3libs.log.setLevel(logging_level)
    gc3utils.log.setLevel(logging_level)


def _get_gcli(config_file_locations, auto_enable_auth=True):
    """
    Return a `gc3libs.gcli.Gcli` instance configured by parsing
    the configuration file(s) located at `config_file_locations`.
    Order of configuration files matters: files read last overwrite
    settings from previously-read ones; list the most specific configuration
    files last.

    If `auto_enable_auth` is `True` (default), then `Gcli` will try to renew
    expired credentials; this requires interaction with the user and will
    certainly fail unless stdin & stdout are connected to a terminal.
    """
    # ensure a configuration file exists in the most specific location
    for location in reversed(config_file_locations):
        if os.access(os.path.dirname(location), os.W_OK|os.X_OK) \
                and not gc3libs.utils.deploy_configuration_file(location, "gc3pie.conf.example"):
            # warn user
            gc3utils.log.warning("No configuration file '%s' was found;"
                                 " a sample one has been copied in that location;"
                                 " please edit it and define resources." % location)
    try:
        (default, resources, authorizations, auto_enable_auth) = gc3libs.gcli.import_config(config_file_locations, auto_enable_auth)
        gc3utils.log.debug('Creating instance of Gcli')
        return gc3libs.gcli.Gcli(default, resources, authorizations, auto_enable_auth)
    except NoResources:
        raise FatalError("No computational resources defined.  Please edit the configuration file '%s'." 
                         % config_file_locations)
    except:
        gc3utils.log.debug("Failed loading config file from '%s'", 
                           str.join("', '", config_file_locations))
        raise
        

#====== Main ========

def gclean(*args, **kw):
    """
    The 'glean' command.
    gclean takes a list of jobids and tries to clean each of them.
    if any of the clean requests will fail, gclean will exit with exitcode 1
    gclean will try anyway to process all requests
    """
    parser = OptionParser(usage="Usage: %prog [options] [JOBIDs]", 
                          version="GC3pie project version 1.0. %prog ")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-f", "--force", action="store_true", dest="force", default=False, help="Force removing job")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    # Assume args are all jobids
    for jobid in args:
        job = gc3libs.Job.get_job(jobid)
        if job.state != gc3libs.Job.State.TERMINATED or options.force == True:
            gc3libs.Job.clean_job(job)
        else:
            gc3utils.log.error("Job %s not in terminal state: ignoring.", job)


def ginfo(*args, **kw):
    """The 'ginfo' command."""
    parser = OptionParser(usage="Usage: %prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    # build list of jobs to query status of
    if len(args) == 0:
        jobs = _get_jobs(_list_job_ids())
    else:
        jobs = [ gc3libs.Job.get_job(jobid) for jobid in args ]

    print (78 * '=')
    for job in jobs:
        for key, value in sorted(job.items()):
            if options.verbosity == 0 and (key.startswith('_') 
                                           or key == 'log' 
                                           or str(value) in ['', '-1']):
                continue
            print("%-20s  %-10s " % (key, value))
        print (78 * '=')


def gsub(*args, **kw):
    """The `gsub` command."""
    # Parse command line arguments
    parser = OptionParser(usage="%prog [options] APPLICATION INPUTFILE [OTHER INPUT FILES]")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-r", "--resource", action="store", dest="resource_name", metavar="STRING", default=None, help='Select resource destination')
    parser.add_option("-d", "--jobdir", action="store", dest="job_local_dir", metavar="STRING", default=gc3libs.Default.JOB_FOLDER_LOCATION, help='Select job local folder location')
    parser.add_option("-c", "--cores", action="store", dest="ncores", metavar="INT", default=0, help='Set number of requested cores')
    parser.add_option("-m", "--memory", action="store", dest="memory_per_core", metavar="INT", default=0, help='Set memory per core request (GB)')
    parser.add_option("-w", "--walltime", action="store", dest="walltime", metavar="INT", default=0, help='Set requested walltime (hours)')
    parser.add_option("-a", "--args", action="store", dest="application_arguments", metavar="STRING", default=None, help='Additional application arguments')

    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    if len(args) < 1:
        raise InvalidUsage('Wrong number of arguments: this commands expects at least 1 arguments: application_tag')

    application_tag = args[0]
    if application_tag == 'gamess':
        if len(args) < 2:
            raise InvalidUsage('Wrong number of arguments: this commands expects at least two arguments.')
        application = gamess.GamessApplication(
            *args[1:], # 1st arg is .INP file path, rest are (optional) additional inputs
            **{ 
                'arguments':options.application_arguments,
                'requested_memory':int(options.memory_per_core),
                'requested_cores':int(options.ncores),
                'requestd_resource':options.resource_name,
                'requested_walltime':int(options.walltime),
                'job_local_dir':options.job_local_dir,
                }
            )
    elif application_tag == 'rosetta':
        if len(args) != 4:
            raise InvalidUsage('Wrong number of arguments: this commands expects exactly three arguments.')
        application = rosetta.RosettaApplication(
            application = args[1],
            inputs = { 
                "-in:file:s":args[2],
                "-in:file:native":args[3],
                },
            outputs = [ os.path.splitext(os.path.basename(args[2]))[0] + '.fasc' ],
            arguments=options.application_arguments,
            requested_memory=options.memory_per_core,
            requested_cores=options.ncores,
            requested_resource=options.resource_name,
            requested_walltime=options.walltime,
            job_local_dir=options.job_local_dir,
            )
    else:
        raise InvalidUsage("Unknown application '%s'" % application_tag)

    _gcli = _get_gcli(_default_config_file_locations)
    if options.resource_name:
        _gcli.select_resource(options.resource_name)
        gc3utils.log.info("Retained only resources: %s (restricted by command-line option '-r %s')",
                          str.join(",", [res['name'] for res in _gcli._resources]), 
                          options.resource_name)

    job = _gcli.gsub(application)

    print("Successfully submitted %s; use the 'gstat' command to monitor its progress." 
          % job.jobid)
    gc3libs.Job.persist_job(job)
    return 0


def gresub(*args, **kw):
    """The `gresub` command: resubmit an already-submitted job with different parameters."""
    # Parse command line arguments
    parser = OptionParser(usage="%prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-r", "--resource", action="store", dest="resource_name", metavar="STRING", default=None, help='Select resource destination')
    parser.add_option("-d", "--jobdir", action="store", dest="job_local_dir", metavar="STRING", default=gc3libs.Default.JOB_FOLDER_LOCATION, help='Select job local folder location')
    parser.add_option("-c", "--cores", action="store", dest="ncores", metavar="INT", default=0, help='Set number of requested cores')
    parser.add_option("-m", "--memory", action="store", dest="memory_per_core", metavar="INT", default=0, help='Set memory per core request (GB)')
    parser.add_option("-w", "--walltime", action="store", dest="walltime", metavar="INT", default=0, help='Set requested walltime (hours)')

    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    if len(args) < 1:
        raise InvalidUsage('Wrong number of arguments: this commands expects at least 1 argument: JOBID')

    _gcli = _get_gcli(_default_config_file_locations)
    if options.resource_name:
        _gcli.select_resource(options.resource_name)
        gc3utils.log.info("Retained only resources: %s (restricted by command-line option '-r %s')",
                          str.join(",", [res['name'] for res in _gcli._resources]), 
                          options.resource_name)

    failed = 0
    for jobid in args:
        job = gc3libs.Job.get_job(jobid.strip())
        try:
            _gcli.gstat(job) # update state
        except Exception, ex:
            # ignore errors, and proceed to resubmission anyway
            gc3utils.log.warning("Could not update state of %s: %s: %s", 
                                 jobid, ex.__class__.__name__, str(ex))
        # kill remote job
        try:
            job = _gcli.gkill(job)
        except Exception, ex:
            # ignore errors, but alert user...
            pass

        try:
            job = _gcli.gsub(job.application, job)
            print("Successfully re-submitted %s; use the 'gstat' command to monitor its progress." 
                  % job.jobid)
            gc3libs.Job.persist_job(job)
        except Exception, ex:
            failed += 1
            gc3utils.log.error("Failed resubmission of job '%s': %s: %s", 
                               jobid, ex.__class__.__name__, str(ex))
    return failed


def gstat(*args, **kw):                        
    """The `gstat` command."""
    parser = OptionParser(usage="Usage: %prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    # build list of jobs to query status of
    if len(args) == 0:
        jobs = _get_jobs(_list_job_ids())
    else:
        jobs = [ gc3libs.Job.get_job(jobid) for jobid in args ]

    try:
        _gcli = _get_gcli(_default_config_file_locations)
        _gcli.gstat(*jobs)
    except Exception, x:
        # FIXME: this `if` can go away once all exceptions do the logging in their ctor.
        if isinstance(x, InvalidUsage):
            raise
        else:
            gc3utils.log.critical('Failed retrieving job state')
            raise

    # Print result
    if len(jobs) == 0:
        print ("No jobs in gc3utils database.")
    else:
        print("%-16s  %-10s" % ("Job ID", "State"))
        print("===========================")
        def cmp_job_ids(a,b):
            return cmp(a.jobid, b.jobid)
        for job in sorted(jobs, cmp=cmp_job_ids):
            print("%-16s  %-10s" % (job, job.state))

    # save jobs back to disk
    for job in jobs:
        gc3libs.Job.persist_job(job)

    return 0


def gget(*args, **kw):
    """ The `gget` command."""
    parser = OptionParser(usage="Usage: %prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)
    
    # FIXME: should take possibly a list of JOBIDs and get files for all of them
    if len(args) != 1:
        raise InvalidUsage("This command requires either one argument (the JOBID) or none.")
    jobid = args[0]

    _gcli = _get_gcli(_default_config_file_locations)
    job_obj = gc3libs.Job.get_job(jobid)

    if job_obj.state == gc3libs.Job.State.TERMINATED:
        if not job_obj.output_retrieved:
            _gcli.gget(job_obj)
            print("Job results successfully retrieved in '%s'\n" % job_obj.download_dir)
            gc3libs.Job.persist_job(job_obj)
        else:
            gc3utils.log.error("Job output already downloaded into '%s'", job_obj.download_dir)
    else: # job not in terminal state
        raise InvalidOperation("Job '%s;' not ready for retrieving results" % job)


def gkill(*args, **kw):
    """
    The `gkill` command.
    gkill takes a list of jobids and tries to kill each of them.
    if any of the clean requests will fail, gkill will exit with exitcode 1
    gkill will try anyway to process all requests
    """
    parser = OptionParser(usage="%prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-f", "--force", action="store_true", dest="force", default=False, help="Force removing job")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    shortview = True

    try:
        _gcli = _get_gcli(_default_config_file_locations)

        # Assume args are all jobids
        for jobid in args:
            try:
                job = gc3libs.Job.get_job(jobid)

                gc3utils.log.debug("gkill: Job '%s' in state %s" % (jobid, job.state))

                if job.state == Job.State.TERMINATED:
                    raise InvalidOperation("Job '%s' is already in terminal state" % job)
                else:
                    job = _gcli.gkill(job)
                    gc3libs.Job.persist_job(job)

                    # or shall we simply return an ack message ?
                    print("Sent request to cancel remote job '%s'."% job)
                    print("It may take a few moments for the job to terminate.")

            except Exception, ex:
                gc3utils.log.error("gkill: Failed canceling Job '%s': %s: %s", 
                                   job, ex.__class__.__name__, str(ex))
                continue

    except Exception, ex:
        raise ("gkill failed: %s: %s" % (ex.__class__.__name__, str(ex)))


def gtail(*args, **kw):
    """The 'gtail' command."""
    parser = OptionParser(usage="Usage: %prog [options] JOBID")
    parser.add_option("-v", "--verbose", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-e", "--stderr", action="store_true", dest="stderr", default=False, help="show stderr of the job")
    parser.add_option("-o", "--stdout", action="store_true", dest="stdout", default=True, help="show stdout of the job (default)")
    parser.add_option("-n", "--lines", dest="num_lines", type=int, default=10, help="output  the  last N lines, instead of the last 10")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    try:
        if len(args) != 1:
            raise InvalidUsage("This command requires exactly one argument: the job ID.")
        
        jobid = args[0]
    
        if options.stderr:
            std = 'stderr'
        else:
            std = 'stdout'
            
        _gcli = _get_gcli(_default_config_file_locations)
    
        job = gc3libs.Job.get_job(jobid)

        if job.state == gc3libs.Job.State.COMPLETED:
            raise Exception('Job results already retrieved')
        if job.state == gc3libs.Job.State.UNKNOWN or job.state == gc3libs.Job.State.SUBMITTED:
            raise Exception('Job output not yet available')

        file_handle = _gcli.tail(job,std)
        for line in file_handle.readlines()[-(options.num_lines):]:
            print line.strip()

        file_handle.close()

    except:
        gc3utils.log.critical('program failed due to: %s' % sys.exc_info()[1])
        raise Exception("gtail failed")


def gnotify(*args, **kw):
    """The gnotify command"""
    parser = OptionParser(usage="Usage: %prog [options] JOBID")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-i", "--include", action="store_true", dest="include_job_results", default=False, help="Include Job's results in notification package")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    if len(args) != 1:
        raise InvalidUsage("This command requires exactly one argument: the Job ID.")
    jobid = args[0]

    job = gc3libs.Job.get_job(jobid)
    return gc3libs.utils.notify(job,options.include_job_results)
    


def glist(*args, **kw):
    """The `glist` command."""
    parser = OptionParser(usage="Usage: %prog [options] resource_name")
    parser.add_option("-v", action="count", dest="verbosity", default=0, help="Set verbosity level")
    parser.add_option("-s", "--short", action="store_true", dest="shortview", help="Short view.")
    parser.add_option("-l", "--long", action="store_false", dest="shortview", help="Long view.")
    (options, args) = parser.parse_args(list(args))
    _configure_logger(options.verbosity)

    # FIXME: should take possibly a list of resource IDs and get files for all of them
    if len(args) != 1:
        raise InvalidUsage("This command requires exactly one argument: the resource name.")
    resource_name = args[0]

    _gcli = _get_gcli(_default_config_file_locations)
    resource_object = _gcli.glist(resource_name)
    if not resource_object is None:
        if resource_object.has_key("name"):
            sys.stdout.write('Resource Name: '+resource_object.name+'\n')
        if resource_object.has_key("total_cores") and resource_object.has_key("free_slots"):
            sys.stdout.write('Cores Total/Free: '+str(resource_object.total_cores)+'/'+str(resource_object.free_slots)+'\n')
        if resource_object.has_key("user_run") and resource_object.has_key("user_queued"):
            sys.stdout.write('User Jobs Running/Queued: '+str(resource_object.user_run)+'/'+str(resource_object.user_queued)+'\n')
        sys.stdout.flush()
    else:
        raise Exception("glist terminated")


## utility functions

def _list_job_ids():
    """
    Return list of Job IDs of all currently defined jobs.
    """
    if not os.path.exists(Default.JOBS_DIR):
        return [ ]
    return os.listdir(Default.JOBS_DIR)


def _get_jobs(job_ids, ignore_failures=True):
    """
    Return list of jobs (gc3libs.Job objects) corresponding to the given Job IDs.

    If `ignore_failures` is `True` (default), errors retrieving a
    job from the persistence layer are ignored and the jobid is
    skipped, therefore the returned list can be shorter than the
    list of Job IDs given as argument.  If `ignore_failures` is
    `False`, then any errors result in the relevant exception being
    re-raised.
    """
    jobs = [ ]
    for jobid in job_ids:
        try:
            jobs.append(Job.get_job(jobid))
        except Exception, ex:
            if ignore_failures:
                gc3libs.log.error("Could not retrieve job '%s' (%s: %s). Ignoring.", 
                                  jobid, ex.__class__.__name__, str(ex))
                continue
            else:
                raise
    return jobs
