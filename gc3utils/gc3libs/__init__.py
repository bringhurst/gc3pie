#! /usr/bin/env python
#
# Copyright (C) 2009-2010 GC3, University of Zurich. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
"""
GC3Libs is a python package for controlling the life-cycle of a Grid
or batch computational job.

GC3Libs provides services for submitting computational jobs to Grids
and batch systems and controlling their execution, persisting job
information, and retrieving the final output.

GC3Libs takes an application-oriented approach to batch computing. A
generic `Application` class provides the basic operations for
controlling remote computations, but different `Application`
subclasses can expose adapted interfaces, focusing on the most
relevant aspects of the application being represented.


Computational job management with GC3Libs
=========================================

The `Application` class constructor provides an interface
for the description of a compute job features, like: executable file
to run, input files to copy to the execution location, output files to
copy back, job memory requirements, etc.

In addition, `Application` objects expose an interface to
control the execution of the associated (remote) computational job;
the data regarding the associated job is exposed through the
`.execution` instance attribute, which is an instance of the
`Run` class.


Computational job specification
-------------------------------

GC3Libs `Application` provide a way to describe
computational job characteristics (program to run, input and output
files, memory/duration requirements, etc.) loosely patterned after
ARC's xRSL_ language.

The description of the computational job is done through keyword
parameters to the `Application` constructor, which see for
details.  Changes in the job characteristics *after* an
`Application` object has been constructed are not currently
supported.

.. _xRSL: http://www.nordugrid.org/documents/xrsl.pdf


Execution model of GC3Libs applications
---------------------------------------

An `Application` can be regarded as an abstraction of an
independent asynchronous computation, i.e., a GC3Libs'
`Application` behaves much like an independent UNIX
process. Indeed, GC3Libs' `Application` objects mimic the
POSIX process interface: `Application` are started by a
parent process, run independently of it, and need to have their final
exit code and output reaped by the calling process.

The following table makes the correspondence between POSIX processes
and GC3Libs' `Application` objects explicit.

+--------------------+----------------+------------------------------------+
|`os` module function|GC3Libs function|purpose                             |
+====================+================+====================================+
|exec                |Gcli.gsub       |start new job                       |
+--------------------+----------------+------------------------------------+
|kill (SIGTERM)      |Gcli.gkill      |terminate executing job             |
+--------------------+----------------+------------------------------------+
|wait (WNOHANG)      |Gcli.gstat      |get job status (running, terminated)|
+--------------------+----------------+------------------------------------+
|-                   |Gcli.gget       |retrieve output                     |
+--------------------+----------------+------------------------------------+

At any given moment, a GC3Libs job is in any one of a set of
pre-defined states, listed in the table below.  The job state is
always available in the `.execution.state` instance property of any
`Application` object.

+------------------+--------------------------------------------------------------+----------------------+
|GC3Libs' Job state|purpose                                                       |can change to         |
+==================+==============================================================+======================+
|NEW               |Job has not yet been submitted/started (i.e., gsub not called)|SUBMITTED (by gsub)   |
+------------------+--------------------------------------------------------------+----------------------+
|SUBMITTED         |Job has been sent to execution resource                       |RUNNING, STOPPED      |
+------------------+--------------------------------------------------------------+----------------------+
|STOPPED           |Trap state: job needs manual intervention (either user-       |                      |
|                  |or sysadmin-level) to resume normal execution                 |TERMINATED (by gkill),| 
|                  |                                                              |SUBMITTED (by miracle)|
+------------------+--------------------------------------------------------------+----------------------+
|RUNNING           |Job is executing on remote resource                           |TERMINATED            |
+------------------+--------------------------------------------------------------+----------------------+
|TERMINATED        |Job execution is finished (correctly or not)                  |                      |
|                  |and will not be resumed                                       |None: final state     |
+------------------+--------------------------------------------------------------+----------------------+

A job that is not in the NEW or TERMINATED state is said to be a "live" job.

When a Job object is first created, it is assigned the state NEW.
After a successful invocation of `Gcli.gsub()`, the Job object is
transitioned to state SUBMITTED.  Further transitions to RUNNING or
STOPPED or TERMINATED state, happen completely independently of the
creator program.  The `Gcli.gstat()` call provides updates on the
status of a job. (Somewhat like the POSIX `wait(..., WNOHANG)` system
call, except that GC3Libs provide explicit RUNNING and STOPPED states,
instead of encoding them into the return value.)

The STOPPED state is a kind of generic "run time error" state: a job
can get into the STOPPED state if its execution is stopped (e.g., a
SIGSTOP is sent to the remote process) or delayed indefinitely (e.g.,
the remote batch system puts the job "on hold"). There is no way a job
can get out of the STOPPED state automatically: all transitions from the
STOPPED state require manual intervention, either by the submitting
user (e.g., cancel the job), or by the remote systems administrator
(e.g., by releasing the hold).

The TERMINATED state is the final state of a job: once a job reaches
it, it cannot get back to any other state. Jobs reach TERMINATED state
regardless of their exit code, or even if a system failure occurred
during remote execution; actually, jobs can reach the TERMINATED
status even if they didn't run at all! Just like POSIX encodes process
termination information in the "return code", the GC3Libs encode
information about abnormal process termination using a set of
pseudo-signal codes in a job's returncode attribute: i.e., if
termination of a job is due to some gird/batch system/middleware
error, the job's `os.WIFSIGNALED(job.returncode)` will be True and the
signal code (as gotten from `os.WTERMSIG(job.returncode)`) will be one
of the following:

======  ============================================================
signal  error condition
======  ============================================================
125     submission to batch system failed
124     remote error (e.g., execution node crashed, batch system misconfigured)
123     data staging failure
122     job killed by batch system / sysadmin
121     job canceled by user
======  ============================================================
"""
__docformat__ = 'reStructuredText'
__version__ = '$Revision$'


import os
import os.path
# NG's default packages install arclib into /opt/nordugrid/lib/pythonX.Y/site-packages;
# add this anyway in case users did not set their PYTHONPATH correctly
import sys
sys.path.append('/opt/nordugrid/lib/python%d.%d/site-packages' 
                % sys.version_info[:2])
import time

import logging
log = logging.getLogger("gc3libs")


import Default
from Exceptions import *
from gc3libs.utils import defproperty, Enum, Log, Struct, safe_repr



class Application(Struct):
    """
    Support for running a generic application with the GC3Libs.
    The following parameters are *required* to create an `Application`
    instance:

    `executable`
      (string) name of the application binary to be
      launched on the remote resource; the specifics of how this is
      handled are dependent on the submission backend, but you may
      always run a script that you upload through the `inputs`
      mechanism by specifying './scriptname' as `executable`.

    `arguments`
      list of command-line arguments to pass to
      `executable`; any object in the list will be converted to
      string via Python ``str()``. Note that, in contrast with the
      UNIX ``execvp()`` usage, the first argument in this list
      will be passed as ``argv[1]``, i.e., ``argv[0]`` will always
      be equal to `executable`.

    `inputs`
      list of files that will be copied from the local
      computer to the remote execution node before execution
      starts. Each item in the list should be a pair
      `(local_file_name, remote_file_name)`; specifying a single
      string `file_name` is allowed as a shortcut and will result
      in both `local_file_name` and `remote_file_name` being
      equal.  If an absolute path name is specified as
      `remote_file_name`, then a warning will be issued and the
      behavior is undefined.

    `outputs`
      list of files that will be copied back from the
      remote execution node back to the local computer after
      execution has completed.  Each item in the list should be a pair
      `(remote_file_name, local_file_name)`; specifying a single
      string `file_name` is allowed as a shortcut and will result
      in both `local_file_name` and `remote_file_name` being
      equal.  If an absolute path name is specified as
      `remote_file_name`, then a warning will be issued and the
      behavior is undefined.

    The following optional parameters may be additionally
    specified as keyword arguments and will be given special
    treatment by the `Application` class logic:

    `requested_cores`,`requested_memory`,`requested_walltime`
      specify resource requirements for the application: the
      number of independent execution units (CPU cores), amount of
      memory (in GB; will be converted to a whole number by
      truncating any decimal digits), amount of wall-clock time to
      allocate for the computational job (in hours; will be
      converted to a whole number by truncating any decimal
      digits).

    `environment`
      a list of pairs `(name, value)`: the
      environment variable whose name is given by the contents of
      the string `name` will be defined as the content of string
      `value` (i.e., as if "export name=value" was executed prior
      to starting the application).  Alternately, one can pass in
      a list of strings of the form "name=value".

    `stdin`
      file name of a file whose contents will be fed as
      standard input stream to the remote-executing process.

    `stdout`
      name of a file where the standard output stream of
      the remote executing process will be redirected to; will be
      automatically added to `outputs`.

    `stderr`
      name of a file where the standard error stream of
      the remote executing process will be redirected to; will be
      automatically added to `outputs`.

    `join`
      if this evaluates to `True`, then standard error is
      redirected to the file specified by `stdout` and `stderr` is
      ignored.  (`join` has no effect if `stdout` is not given.)

    `tags`
      list of tag names (string) that must be present on a
      resource in order to be eligible for submission; in the ARC
      backend, tags are interpreted as run-time environments (RTE) to
      request.  name).

    Any other keyword arguments will be set as instance attributes,
    but otherwise ignored by the `Application` constructor.

    After successful construction, an `Application` object is
    guaranteed to have the following instance attributes:

    `executable`
      a string specifying the executable name

    `arguments`
      list of strings specifying command-line arguments for executable
      invocation; possibly empty

    `inputs`
      dictionary mapping local file name (a string) to a remote file name (a string)

    `outputs`
      dictionary mapping remote file name (a string) to a local file name (a string)

    `output_dir`
      Path to the base directory where output files were last
      downloaded to, or `None` if no output files have been downloaded
      yet.

    `output_retrieved` 
      boolean flag, indicating whether job output has been fetched
      from the remote resource; use the Gcli.gget() function to
      retrieve the output. (Note: for jobs in TERMINATED state, the
      output can be retrieved only once!)

    `environment`
      dictionary mapping environment variable names to the requested
      value (string); possibly empty

    `stdin`
      `None` or a string specifying a (local) file name.  If `stdin`
      is not None, then it matches a key name in `inputs`

    `stdout`
      `None` or a string specifying a (remote) file name.  If `stdout`
      is not None, then it matches a key name in `outputs`

    `stderr`
      `None` or a string specifying a (remote) file name.  If `stdout`
      is not None, then it matches a key name in `outputs`

    `join`
      boolean value, indicating whether `stdout` and `stderr` are
      collected into the same file

    `tags`
      list of strings specifying the tags to request in each resource
      for submission; possibly empty.
    """
    def __init__(self, executable, arguments, inputs, outputs, **kw):
        # required parameters
        self.executable = executable
        self.arguments = [ str(x) for x in arguments ]

        def convert_to_tuple(val):
            if isinstance(val, (str, unicode)):
                l = str(val)
                r = os.path.basename(l)
                return (l, r)
            else: 
                return tuple(val)
        self.inputs = dict([ convert_to_tuple(x) for x in inputs ])
        self.outputs = dict([ convert_to_tuple(x) for x in outputs ])

        # optional params
        def get_and_remove(dictionary, key, default=None, verbose=False):
            if dictionary.has_key(key):
                result = dictionary[key]
                del dictionary[key]
            else:
                result = default
            if verbose:
                log.info("Using value '%s' for 'Application.%s'", result, key)
            return result
        # FIXME: should use appropriate unit classes for requested_*
        self.requested_cores = get_and_remove(kw, 'requested_cores')
        self.requested_memory = get_and_remove(kw, 'requested_memory')
        self.requested_walltime = get_and_remove(kw, 'requested_walltime')

        self.environment = get_and_remove(kw, 'environment', {})
        def to_env_pair(val):
            if isinstance(val, tuple):
                return val
            else:
                # assume `val` is a string
                return tuple(val.split('=', 1))
        self.environment = dict([ to_env_pair(x) for x in self.environment.items() ])

        self.join = get_and_remove(kw, 'join', False)
        self.stdin = get_and_remove(kw, 'stdin')
        if self.stdin and self.stdin not in self.inputs:
            self.input[self.stdin] = os.path.basename(self.stdin)
        self.stdout = get_and_remove(kw, 'stdout')
        if self.stdout and self.stdout not in self.outputs:
            self.outputs[self.stdout] = os.path.basename(self.stdout)
        self.stderr = get_and_remove(kw, 'stderr')
        if self.stderr and self.stderr not in self.outputs:
            self.outputs[self.stderr] = os.path.basename(self.stderr)

        self.tags = get_and_remove(kw, 'tags', [])

        # job name
        self.jobname = get_and_remove(kw, 'jobname', self.__class__.__name__)

        # execution
        self.execution = Run()
        self.execution.attach(self)

        # output management
        self.output_dir = None
        self.output_retrieved = False

        # any additional param
        Struct.__init__(self, **kw)


    def __str__(self):
        try:
            return str(self._id)
        except AttributeError:
            return safe_repr(self)

        
    def clone():
        """
        Return a deep copy of this `Application` object, with the
        `.execution` instance variable reset to a fresh new instance
        of `Run`.
        """
        return Application(**self)


    def xrsl(self, resource):
        """
        Return a string containing an xRSL sequence, suitable for
        submitting an instance of this application through ARC's
        ``ngsub`` command.

        The default implementation produces XRSL content based on 
        the construction parameters; you should override this method
        to produce XRSL tailored to your application.
        """
        xrsl= str.join(' ', [
                '&',
                '(executable="%s")' % self.executable,
                '(arguments=%s)' % str.join(' ', [('"%s"' % x) for x in self.arguments]),
                '(gmlog="gmlog")', # FIXME: should check if conflicts with any input/output files
                ])
        if (os.path.basename(self.executable) in self.inputs
            or './'+os.path.basename(self.executable) in self.inputs):
            xrsl += '(executables="%s")' % os.path.basename(self.executable)
        if self.stdin:
            xrsl += '(stdin="%s")' % self.stdin
        if self.join:
            xrsl += '(join="yes")'
        else:
            xrsl += '(join="no")'
        if self.stdout:
            xrsl += '(stdout="%s")' % self.stdout
        if self.stderr and not self.join:
            xrsl += '(stderr="%s")' % self.stderr
        if len(self.inputs) > 0:
            xrsl += ('(inputFiles=%s)' 
                     % str.join(' ', [ ('("%s" "%s")' % (r,l)) for (l,r) in self.inputs.items() ]))
        if len(self.outputs) > 0:
            xrsl += ('(outputFiles=%s)'
                     % str.join(' ', [ ('("%s" "%s")' % rl) 
                                       for rl in [ _filtered 
                                                   for _filtered in self.outputs.items() 
                                                   if (_filtered[0] != self.stdout 
                                                       and _filtered[0] != self.stderr)]]))
        if len(self.tags) > 0:
            xrsl += str.join('\n', [
                    ('(runTimeEnvironment>="%s")' % rte) for rte in self.tags ])
        if len(self.environment) > 0:
            xrsl += ('(environment=%s)' % 
                     str.join(' ', [ ('("%s" "%s")' % kv) for kv in self.environment ]))
        if self.requested_walltime:
            xrsl += '(wallTime="%d hours")' % self.requested_walltime
        if self.requested_memory:
            xrsl += '(memory="%d")' % (1000 * self.requested_memory)
        if self.requested_cores:
            xrsl += '(count="%d")' % self.requested_cores
        if self.jobname:
            xrsl += '(jobname="%s")' % self.jobname

        return xrsl


    def cmdline(self, resource):
        """
        Return a string, suitable for invoking the application from a
        UNIX shell command-line.

        The default implementation just concatenates `executable` and
        `arguments` separating them with whitespace; this is hardly
        correct for any application, so you should override this
        method in derived classes to provide appropriate invocation
        templates.
        """
        return str.join(" ", [self.executable] + self.arguments)


    def qsub(self, resource, _suppress_warning=False, **kw):
        # XXX: the `_suppress_warning` switch is only provided for
        # some applications to make use of this generic method without
        # logging the user-level warning, because, e.g., it has already
        # been taken care in some other way (cf. GAMESS' `qgms`).
        # Use with care and don't depend on it!
        """
        Get an SGE ``qsub`` command-line invocation for submitting an
        instance of this application.  Return a pair `(cmd, script)`,
        where `cmd` is the command to run to submit an instance of
        this application to the SGE batch system, and `script` --if
        it's not `None`-- is written to a new file, whose name is then
        appended to `cmd`.

        In the construction of the command-line invocation, one should
        assume that all the input files (as named in `Application.inputs`)
        have been copied to the current working directory, and that output
        files should be created in this same directory.

        The default implementation just prefixes any output from the
        `cmdline` method with an SGE ``qsub`` invocation of the form
        ``qsub -cwd -S /bin/sh`` + resource limits.  Note that 
        *there is no generic way of requesting a certain number of cores* 
        in SGE: it all depends on the installed parallel environment, and
        these are totally under control of the local sysadmin;
        therefore, any request for cores is ignored and a warning is
        logged.

        You definitely want to override this method in
        application-specific classes to provide appropriate invocation
        templates.
        """
        qsub = 'qsub -cwd -S /bin/sh '
        if self.requested_walltime:
            # SGE uses `s_rt` for wall-clock time limit, expressed in seconds
            qsub += ' -l s_rt=%d' % (3600 * self.requested_walltime)
        if self.requested_memory:
            # SGE uses `mem_free` for memory limits; 'G' suffix allowed for Gigabytes
            qsub += ' -l mem_free=%dG' % self.requested_memory
        if self.requested_cores and not _suppress_warning:
            # XXX: should this be an error instead?
            log.warning("Application requested %d cores,"
                        " but there is no generic way of expressing this requirement in SGE!"
                        " Ignoring request, but this will likely result in malfunctioning later on.", 
                        self.requested_cores)
        if self.job_name:
            qsub += " -N '%s'" % self.job_name
        return (qsub, self.cmdline(resource))



class _Signal(object):
    """
    Base class for representing fake signals encoding the failure
    reason for GC3Libs jobs.
    """
    def __init__(self, name, signum, description):
        self._name = name
        self._signum = signum
        self.__doc__ = description
    # conversion to integer types
    def __int__(self):
        return self._signum
    def __long__(self):
        return self._signum
    # human-readable explanation
    def __str__(self):
        return "SIG%s(%d) - %s" % (self._name, self._signum, self.__doc__)


class Run(Struct):
    """
    A specialized `dict`-like object that keeps information about
    the execution state of an `Application` instance.

    A `Run` object is guaranteed to have the following attributes:

      * `state`: Current state of the job, initially `State.NEW`; 
         see `Run.State` for a list of the possible values.

      * `output_dir`: path to the directory where output has been
        downloaded, or `None` if no output has been retrieved yet.

      * `output_retrieved`: Initially, `False`, set to `True` after a
        successful call to `Gcli.gget`

    `Run` objects support attribute lookup by both the ``[...]`` and
    the ``.`` syntax; see `gc3libs.utils.Struct` for examples.
    """
    def __init__(self,initializer=None,**keywd):
        """
        Create a new Run object; constructor accepts the same
        arguments as the `dict` constructor.
        
        Examples:
        
          1. Create a new job with default parameters::

            >>> j1 = Run()
            >>> j1.returncode
            None
            >>> j1.state
            'NEW'

          2. Create a new job with additional attributes::

            >>> j2 = Run(application='GAMESS', version='2010R1')
            >>> j2.state
            'NEW'
            >>> j2.application
            'GAMESS'
            >>> j2['version']
            '2010R1'

          3. Clone an existing job object::

            >>> j3 = Run(j2)
            >>> j3.application
            'GAMESS'
            >>> j3['version']
            '2010R1'
            
        """
        if not hasattr(self, '_state'): self._state = Run.State.NEW
        self._exitcode = None
        self._signal = None

        Struct.__init__(self, initializer, **keywd)

        if 'log' not in self: self.log = Log()
        if 'output_retrieved' not in self: self.output_retrieved = False
        if 'timestamp' not in self: self.timestamp = { }

    
    def attach(self, observer):
        """
        Notify `observer` of any changes to the execution state.

        Only one observer will receive notifications; this overrides
        any previously-set observer.
        """
        self._observer = observer

    def detach(self):
        """
        Stop notifying any observer of execution state changes.
        """
        self._observer = None


    # states that a `Run` can be in
    State = Enum(
        'NEW',       # Job has not yet been submitted/started
        'SUBMITTED', # Job has been sent to execution resource
        'STOPPED',   # trap state: job needs manual intervention
        'RUNNING',   # job is executing on remote resource
        'TERMINATED',# job execution finished (correctly or not) and will not be resumed
        'UNKNOWN',   # job info not found or lost track of job (e.g., network error or invalid job ID)
        )

    @defproperty
    def state():
        """
        The state a `Run` is in; see `Run.State` for possible values.
        The value of `Run.state` must always be a value from the
        `Run.State` enumeration.
        """
        def fget(self):
            return self._state
        def fset(self, value):
            if value not in Run.State:
                raise ValueError("Value '%s' is not a legal `gc3libs.Run.State` value." % value)
            if self._state != value:
                self.timestamp[value] = time.time()
                self.log.append('%s on %s' % (value, time.asctime()))
            self._state = value
            # call state transition methods on observer, if they exist
            observer = self._observer
            if observer is not None:
                handler_name = str(self._state).lower()
                if hasattr(observer, handler_name):
                    getattr(observer, handler_name)()
        return locals()


    @defproperty
    def signal():
        """
        The "signal number" part of a `Run.returncode`, see
        `os.WTERMSIG` for details. 

        The "signal number" is a 7-bit integer value in the range
        0..127; value `0` is used to mean that no signal has been
        received during the application runtime (i.e., the application
        terminated by calling ``exit()``).  

        The value represents either a real UNIX system signal, or a
        "fake" one that GC3Libs uses to represent Grid middleware
        errors (see `Run.Signals`).
        """
        def fget(self): 
            return self._signal
        def fset(self, value): 
            if value is None:
                self._signal = None
            else:
                self._signal = int(value) & 0x7f
        return (locals())


    @defproperty
    def exitcode():
        """
        The "exit code" part of a `Run.returncode`, see
        `os.WEXITSTATUS`.  This is an 8-bit integer, whose meaning is
        entirely application-specific.  However, the value `-1` is
        used to mean that an error has occurred and the application
        could not end its execution normally.
        """
        def fget(self):
            return self._exitcode
        def fset(self, value):
            if value is None:
                self._exitcode = None
            else:
                self._exitcode = int(value) & 0xff
        return (locals())


    @defproperty
    def returncode():
        """
        The `returncode` attribute of this job object encodes the
        `Run` termination status in a manner compatible with the POSIX
        termination status as implemented by `os.WIFSIGNALED()` and
        `os.WIFEXITED()`.

        However, in contrast with POSIX usage, the `exitcode` and the
        `signal` part can *both* be significant: in case a Grid
        middleware error happened *after* the application has
        successfully completed its execution.  In other words,
        `os.WEXITSTATUS(job.returncode)` is meaningful iff
        `os.WTERMSIG(job.returncode)` is 0 or one of the
        pseudo-signals listed in `Run.Signals`.
        
        `Run.exitcode` and `Run.signal` are combined to form the
        return code 16-bit integer as follows (the convention appears
        to be obeyed on every known system):

           +------+------------------------------------+
           |Bit   |Encodes...                          |
           +======+====================================+
           |0..7  |signal number                       |
           +------+------------------------------------+
           |8     |1 if program dumped core.           |
           +------+------------------------------------+
           |9..16 |exit code                           |
           +------+------------------------------------+

        *Note:* the "core dump bit" is always 0 here.

        Setting the `returncode` property sets `exitcode` and
        `signal`; you can either assign a `(signal, exitcode)` pair to
        `returncode`, or set `returncode` to an integer from which the
        correct `exitcode` and `signal` attribute values are
        extracted::

           >>> j = Run()
           >>> j.returncode = (42, 56)
           >>> j.signal
           42
           >>> j.exitcode
           56

           >>> j.returncode = 137
           >>> j.signal
           9
           >>> j.exitcode
           0

        See also `Run.exitcode` and `Run.signal`.
        """
        def fget(self): 
            if self.exitcode is None and self.signal is None:
                return None
            if self.exitcode is None:
                exitcode = -1
            else:
                exitcode = self.exitcode
            if self.signal is None:
                signal = 0
            else: 
                signal = self.signal
            return (exitcode << 8) | signal
        def fset(self, value):
            try:
                # `value` can be a tuple `(signal, exitcode)`
                self.signal = int(value[0])
                self.exitcode = int(value[1])
            except TypeError:
                self.exitcode = (int(value) >> 8) & 0xff
                self.signal = int(value) & 0x7f
            # ensure values are within allowed range
            self.exitcode &= 0xff
            self.signal &= 0x7f
        return (locals())

    class Signals(object):
        """
        Collection of (fake) signals used to encode termination reason in `Job.returncode`.
        """
        Cancelled = _Signal('CANCEL', 121, "Job canceled by user")
        RemoteKill = _Signal('BATCHKILL', 122, "Job killed by batch system or sysadmin")
        DataStagingFailure = _Signal('STAGE', 123, "Data staging failure")
        RemoteError = _Signal('BATCHERR', 124, 
                              "Unspecified remote error, e.g., execution node crashed"
                              " or batch system misconfigured")
        SubmissionFailed = _Signal('SUBMIT', 125, "Submission to batch system failed.")


        



## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(name="__init__",
                    optionflags=doctest.NORMALIZE_WHITESPACE)
