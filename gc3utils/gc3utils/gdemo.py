#!/usr/bin/env python
#
"""
Implementation of the `demonstration` command-line front-ends.
"""
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
__docformat__ = 'reStructuredText'
__version__ = '$Revision$'
__docformat__='reStructuredText'
__version__ = '$Revision$'

__author__="Sergio Maffioletti <sergio.maffioletti@gc3.uzh.ch>, Riccardo Murri <riccardo.murri@uzh.ch>"
__date__ = '$Date$'
__copyright__="Copyright (c) 2009,2010 Grid Computing Competence Center, University of Zurich"

import sys
import os
import time

from optparse import OptionParser

from gc3libs import Application, Run
import gc3libs.application.demo as demo
import gc3libs.Default as Default
from   gc3libs.Exceptions import *
import gc3libs.core as core
import gc3libs.utils as utils

# import gc3utils


# defaults - XXX: do they belong in ../core.py instead?
_homedir = os.path.expandvars('$HOME')
_rcdir = _homedir + "/.gc3"
config_file_locations = [ "/etc/gc3/gc3pie.conf", _rcdir + "/gc3pie.conf" ]
_default_joblist_file = _rcdir + "/.joblist"
_default_joblist_lock = _rcdir + "/.joblist_lock"
_default_job_folder_location = os.getcwd()


def main():
    # We will skip argument parsing and all other decorative tasks
    # 1) obtain instance on core
    # 2) create application instance
    # 3) submit application
    # 4) monitor status (loop)
    # 5) retrieve results
    # 6) display status log
    # 7) exit
    
    # 0) parse command line arguments
    parser = OptionParser(usage="%prog INPUTFILE")
    (options, args) = parser.parse_args(sys.argv[1:])

    if len(args) < 1:
        raise InvalidUsage('Wrong number of arguments: this commands expects at exactly 1 argument: file containing the list of integer to be calculated')

    # 1) obtain instance on core
    print("Creating instance of core... ")
    try:
        _core = gc3libs.core.Core(* gc3libs.core.import_config(config_file_locations, True))
    except NoResources:
        raise FatalError("No computational resources defined.  Please edit the configuration file '%s'."
                         % config_file_locations)
    except:
        gc3utils.log.debug("Failed loading config file from '%s'",
                           str.join("', '", config_file_locations))
        raise

    print("Creating instance of application... ")
    # 2) create application instance
    app = demo.Square(
        args[0], # 1st arg is .txt file path containing a list of integer to be calculated
        requested_memory = '1',
        requested_cores = '1',
        requested_walltime = '1'
        )

    print("Submitting... ")
    # 3) submit application  
    _core.submit(app)


    print("Looping over running state... ")
    # 4) monitor status (loop)
    while app.execution.state != Run.State.TERMINATED:
        try:
            _core.update_job_state(app)
            time.sleep(10)
        except:
            raise
        
    print("retrieving results... ")
    #  5) retrieve results
    _core.fetch_output(app, app.output_dir, overwrite=False)

    # 5.1) clean application: remove remote data
    _core.free(app)

    # 6) display status log 
    print("Application termianted")
    print (78 * '=')
    for key, value in sorted(app.execution.items()):  
        print("%-20s  %-10s " % (key, value)) 
        print (78 * '=')

        #print("Status: %s" % app.execution.state)
        #print("Return code: %d" % app.execution.returncode)
        #print("Exit code: %d" % app.execution.exitcode)
        #print("Results retrieved in %s" % app.output_dir)

    print("Done ")
    # 7) exit
    return app.execution.returncode

if "__main__" == __name__:
    sys.exit(main())

