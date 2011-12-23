#! /usr/bin/env python
#
#   ggeotop.py -- Front-end script for submitting multiple `GEOtop` jobs to SMSCG.
#
#   Copyright (C) 2011 GC3, University of Zurich
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Front-end script for submitting multiple `GEOtop` jobs to SMSCG.
It uses the generic `gc3libs.cmdline.SessionBasedScript` framework.

See the output of ``ggeotop --help`` for program usage instructions.
"""
__version__ = 'development version (SVN $Revision$)'
# summary of user-visible changes
__changelog__ = """
  2011-11-07:
    * Initial release, forked off the ``gmhc_coev`` sources.
"""
__author__ = 'Riccardo Murri <riccardo.murri@uzh.ch>'
__docformat__ = 'reStructuredText'


# ugly workaround for Issue 95,
# see: http://code.google.com/p/gc3pie/issues/detail?id=95
if __name__ == "__main__":
    import ggeotop


# std module imports
import csv
import glob
import math
import os
import posix
import re
import shutil
import sys
import time

import tarfile

from pkg_resources import Requirement, resource_filename

# gc3 library imports
import gc3libs
from gc3libs import Application, Run, Task, RetryableTask
from gc3libs.cmdline import SessionBasedScript, executable_file
import gc3libs.utils


GC3PIE_PLACEHOLDER_FILENAME = ".gc3pie_placeholder"
GEOTOP_INPUT_ARCHIVE = "input.tgz"
GEOTOP_OUTPUT_ARCHIVE = "output.tgz"

## custom application class

class GeotopApplication(Application):
    """
    Custom class to wrap the execution of the ``GEOtop` program.

    For more information about GEOtop, see <http://www.goetop.org/>
    """
    def __init__(self, simulation_dir, executable=None, **kw):
        # remember for later
        self.simulation_dir = simulation_dir
        # stage all (non-hidden) files in the simulation directory for input

        def scan_and_tar(simulation_dir):
            def geotop_exclude(filename):
                return filename.endswith('~') \
                       or filename.endswith('ggeotop.log') \
                       or filename.endswith('_static') \
                       or filename.endswith('geotop.log') \
                       or filename.endswith(GEOTOP_OUTPUT_ARCHIVE) \
                       or filename.endswith(GEOTOP_INPUT_ARCHIVE) \
                       or filename.startswith('./.arc')        

            try:
                gc3libs.log.debug("Compressing input folder '%s'" % simulation_dir)
                cwd = os.getcwd()
                os.chdir(simulation_dir)
                # check if input archive already present. If so, remove it
                if os.path.isfile(GEOTOP_INPUT_ARCHIVE):
                    try:
                        os.remove(GEOTOP_INPUT_ARCHIVE)
                    except OSError as x:
                        gc3libs.log.error("Failed while removing %s. Type %s. Message %s" % (GEOTOP_INPUT_ARCHIVE, x.__class__, x.message))
                        pass

                tar = tarfile.open(GEOTOP_INPUT_ARCHIVE, "w:gz")
                tar.add('.',recursive=True,exclude=geotop_exclude)
                tar.close()
                os.chdir(cwd)
                yield (tar.name, GEOTOP_INPUT_ARCHIVE)
            except:
                raise

        # def walk_input_folder(simulation_dir):
        #     exclude_patterns = ['~','.arc','/in']
        #     for r,d,f in os.walk(simulation_dir):
        #         if r.endswith('~') or r.endswith('.arc') or r.endswith('/in'):
        #             continue
        #         for filename in f:
        #             # full_filename = os.path.join(r,filename)
        #             # remote_entry_filename = full_filename.split(simulation_dir)[1]
        #             yield (os.path.join(r,filename),"")
            
        # def fill_empty_folder(simulation_dir):
        #     for dirpath, dirnames, filenames in os.walk(simulation_dir):
        #         entry = os.path.basename(dirpath)
        #         if not entry.endswith('~'):
        #             if not dirnames and not filenames:
        #                 # Folder is empty; fill it with a 'placeholder' file
        #                 try:
        #                     f = open(os.path.join(dirpath, GC3PIE_PLACEHOLDER_FILENAME),"w+")
        #                     f.close()
        #                     yield ((os.path.join(dirpath, GC3PIE_PLACEHOLDER_FILENAME),
        #                             os.path.join(entry, GC3PIE_PLACEHOLDER_FILENAME)))
        #                 except IOError:
        #                     raise
        #             else:
        #                 for f in filenames:
        #                     if dirpath == simulation_dir:
        #                         yield(os.path.join(dirpath,f),f)
        #                     else:
        #                         yield (os.path.join(dirpath,f),os.path.join(entry,f))


        # inputs = dict((a,b) for (a,b) in fill_empty_folder(simulation_dir))

        inputs = dict((a,b) for (a,b) in scan_and_tar(simulation_dir))

        ## XXX: convention is that 'in' folder contains only input values that should not
        ## be retrieved as part of the output
        # outputs = {}
        # outputs[GEOTOP_OUTPUT_ARCHIVE] = GEOTOP_OUTPUT_ARCHIVE
        
        geotop_wrapper_sh = resource_filename(Requirement.parse("gc3pie"),
                                              "gc3libs/etc/geotop_wrap.sh")

        inputs[geotop_wrapper_sh] = os.path.basename(geotop_wrapper_sh)

        if executable is not None:
            # use the specified executable
            executable_name = './' + os.path.basename(executable)
            inputs[executable] = os.path.basename(executable)
        else:
            raise NotImplementedError("No RTE for GEOtop defined; please specify an executable!")
            # use the default one provided by the RTE
            executable_name = '/$GEOTOP'

        # outputs = {}
        # outputs[GEOTOP_OUTPUT_ARCHIVE] = GEOTOP_OUTPUT_ARCHIVE
        # set some execution defaults...
        kw.setdefault('requested_cores', 1)
        kw.setdefault('requested_architecture', Run.Arch.X86_64)
        kw.setdefault('requested_walltime',16)
        # ...and remove excess ones
        kw.pop('output_dir', None)
        Application.__init__(
            self,
            # executable = executable_name,
            executable = os.path.basename(geotop_wrapper_sh),
            # GEOtop requires only one argument: the simulation directory
            # In our case, since all input files are staged to the
            # execution directory, the only argument is fixed to ``.``
            arguments = [ 'input.tgz', executable_name ],
            inputs = inputs,
            outputs = gc3libs.ANY_OUTPUT,
            # outputs = outputs,
            output_dir = os.path.join(simulation_dir, 'out'),
            stdout = 'ggeotop.log',
            join=True,
            #tags = [ 'APPS/GEOTOP-1.223' ],
            **kw)


    def terminated(self):
        """
        Analyze the retrieved output and decide whether to submit
        another run or not, depending on whether tag files named
        ``_SUCCESSFUL_RUN`` or ``_FAILED_RUN`` are found.
        """

        
        # provisionally set exit code to 99 (resubmit), will override
        # later if the tag files ``_SUCCESSFUL_RUN`` or
        # ``_FAILED_RUN`` are found.
        self.execution.returncode = (0, 99)

        full_tarname = os.path.join(self.output_dir,GEOTOP_OUTPUT_ARCHIVE)

        # check and unpack output archive
        if os.path.isfile(full_tarname):
            # execution should have been completed sucessfully
            # untar archive
            gc3libs.log.info("Expected output archive found in %s" % full_tarname)
            
            try:
                tar = tarfile.open(full_tarname)
                tar.extractall(path=self.simulation_dir)
                tar.close()
                os.remove(full_tarname)
            except Exception, ex:
                gc3libs.log.error("Failed while opening archive. Error type %s. Message %s" % (x.__class__, x.message))
                pass
        
        tmp_output_dir = self.output_dir
        exclude = [
            os.path.basename(self.executable),
            self.stdout,
            self.stderr,
            ]

        # # move files one level up
        # # subprocess.call(args, *, stdin=None, stdout=None, stderr=None, shell=False)
        # try:
        #     for entry in os.listdir(tmp_output_dir):
        #         dest_entry = os.path.join(self.simulation_dir, entry)
        #         _command = "mv --update %s/* %s/" % (entry,dest_dir)
        #         _command = shlex.split(_command)
        #         subprocess.call(_command)
        # except Exception, x:
        #     gc3libs.log.error("Failed running %s. Error type %s. Message %s" % (_command,x.__class__,x.message))
        #     pass
    
        # move files one level up, except the ones listed in `exclude`
        for entry in os.listdir(tmp_output_dir):
            src_entry = os.path.join(tmp_output_dir, entry)
            # concatenate all output files together
            if entry == self.stdout:
                gc3libs.utils.cat(src_entry, output=os.path.join(self.simulation_dir, entry), append=True)
                # try remove it
                os.remove(src_entry)
                continue
            if entry == self.stderr:
                gc3libs.utils.cat(src_entry, output=os.path.join(self.simulation_dir, entry), append=True)
                # try remove it
                os.remove(src_entry)
                continue
            if entry in exclude or (entry.startswith('script.') and entry.endswith('.sh')):
                # delete entry and continue with next one
                os.remove(src_entry)
                continue
            # # special files indicate successful or unsuccessful completion
            # if entry in [ '_SUCCESSFUL_RUN', '_SUCCESSFUL_RUN.old' ]:
            #     # if .R then run 'R CMD <filename>.R' on the .R
            #     # self._execute_postprocess()
            #     self.execution.returncode = (0, posix.EX_OK)
            # elif entry in [ '_FAILED_RUN', '_FAILED_RUN.old' ]:
            #     # use exit code 100 to indicate total failure
            #     self.execution.returncode = (0, 100)
            # now really move file one level up
            dest_entry = os.path.join(self.simulation_dir, entry)
            if os.path.exists(dest_entry):
                # backup with numerical suffix
                # gc3libs.utils.backup(dest_entry)
                shutil.rmtree(dest_entry, ignore_errors=True)
            os.rename(os.path.join(tmp_output_dir, entry), dest_entry)
        # os.removedirs(tmp_output_dir)
        shutil.rmtree(tmp_output_dir, ignore_errors=True)

        # search for termination files
        if os.path.isfile(os.path.join(self.simulation_dir,'_SUCCESSFUL_RUN')) or os.path.isfile(os.path.join(self.simulation_dir,'_SUCCESSFUL_RUN.old')):
            self.execution.returncode = (0, posix.EX_OK)
        elif os.path.isfile(os.path.join(self.simulation_dir,'_FAILED_RUN')) or os.path.isfile(os.path.join(self.simulation_dir,'_FAILED_RUN.old')):
            # use exit code 100 to indicate total failure
            self.execution.returncode = (0, 100)


class GeotopTask(RetryableTask, gc3libs.utils.Struct):

    def __init__(self, simulation_dir, executable=None, **kw):
        RetryableTask.__init__(
            self,
            # task name
            os.path.basename(simulation_dir),
            # actual computational job
            GeotopApplication(simulation_dir, executable, **kw),
            # keyword arguments
            **kw)

    def retry(self):
        """
        Resubmit a GEOtop application instance iff it exited with code 99.

        *Note:* There is currently no upper limit on the number of
        resubmissions!
        """
        if self.task.execution.exitcode == 99:
            return True
        else:
            return False


## main script class
            
class GGeotopScript(SessionBasedScript):
    """
Scan the specified INPUT directories recursively for simulation
directories and submit a job for each one found; job progress is
monitored and, when a job is done, its output files are retrieved back
into the simulation directory itself.

A simulation directory is defined as a directory containing a
``geotop.inpts`` file.

The ``ggeotop`` command keeps a record of jobs (submitted, executed
and pending) in a session file (set name with the ``-s`` option); at
each invocation of the command, the status of all recorded jobs is
updated, output from finished jobs is collected, and a summary table
of all known jobs is printed.  New jobs are added to the session if
new input files are added to the command line.

Options can specify a maximum number of jobs that should be in
'SUBMITTED' or 'RUNNING' state; ``ggeotop`` will delay submission of
newly-created jobs so that this limit is never exceeded.
    """

    def __init__(self):
        SessionBasedScript.__init__(
            self,
            version = __version__, # module version == script version
            application = ggeotop.GeotopTask,
            # only display stats for the top-level policy objects
            # (which correspond to the processed files) omit counting
            # actual applications because their number varies over
            # time as checkpointing and re-submission takes place.
            stats_only_for = ggeotop.GeotopTask,
            )

    def setup_options(self):
        self.add_param("-x", "--executable", metavar="PATH", #type=executable_file,
                       dest="executable", default=None,
                       help="Path to the GEOtop executable file.")
        # change default for the "-o"/"--output" option
        #self.actions['output'].default = 'NPOPSIZE/PARAMS/ITERATION'


    def parse_args(self):
        """
        Check validity and consistency of command-line options.
        """
        if self.params.executable is None:
            raise gc3libs.exceptions.InvalidUsage(
                "Use the '-x' option to specify a valid path to the GEOtop executable.")
        if not os.path.exists(self.params.executable):
            raise gc3libs.exceptions.InvalidUsage(
                "Path '%s' to the GEOtop executable does not exist;"
                " use the '-x' option to specify a valid one."
                % self.params.executable)
        gc3libs.utils.test_file(self.params.executable, os.R_OK|os.X_OK,
                                gc3libs.exceptions.InvalidUsage)


    def new_tasks(self, extra):
        input_files = self._search_for_input_files(self.params.args, 'geotop.inpts')

        # the real input to GEOtop are the directories containing `geotop.inpts`
        input_dirs = [ (os.path.dirname(path) or os.getcwd())
                       for path in input_files ]

        for path in input_dirs:
            # construct GEOtop job
            yield (
                # job name
                gc3libs.utils.basename_sans(path),
                # task constructor
                ggeotop.GeotopTask,
                [ # parameters passed to the constructor, see `GeotopTask.__init__`
                    path,                   # path to the directory containing input files
                    self.params.executable, # path to the GEOtop executable
                ],
                # extra keyword arguments passed to the constructor,
                # see `GeotopTask.__init__`
                extra.copy()
                )

        

# run it
if __name__ == '__main__':
    GGeotopScript().run()