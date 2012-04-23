#! /usr/bin/env python
#
"""
Support for AppPot-hosted applications.

For more details about AppPot, visit:
<http://apppot.googlecode.com>
"""
# Copyright (C) 2011, 2012, GC3, University of Zurich. All rights reserved.
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

import gc3libs


class AppPotApplication(gc3libs.Application):
    """
    Base class for AppPot-hosted applications.
    Provides the same interface as the base `Application`:class:
    and runs the specified command in an AppPot instance.

    In addition to the standard `Application`:class: keyword
    arguments, the following ones can be given to steer the AppPot
    execution:

    * `apppot_img`: Path or URL to the AppPot system image to use.
      If ``None`` (default), then the default AppPot system image
      on the remote system is used.
    """
    def __init__(self, executable, arguments, inputs, outputs, output_dir,
                 apppot_img=None, apppot_changes=None, apppot_tag='ENV/APPPOT-0.21',
                 apppot_extra=[], **kw):
        # AppPot-specific setup
        apppot_start_args = [] 
        if apppot_img is not None:
            AppPotApplication._add_to_inputs(inputs, apppot_img, 'apppot.img')
            apppot_start_args += ['--apppot', 'apppot.img']
        if apppot_changes is not None:
            AppPotApplication._add_to_inputs(inputs, apppot_changes, 'apppot.changes.tar.gz')
            apppot_start_args += ['--changes', 'apppot.changes.tar.gz']
        if kw.has_key('requested_memory'):
            apppot_start_args += ['--mem', ("%dM" % (int(kw['requested_memory']) * 1000))]
            # FIXME: we need to remove the memory limit because batch
            # systems miscompute the amount of memory actually used by
            # an UMLx process...
            del kw['requested_memory']
        if apppot_extra:
            for arg in apppot_extra:
                apppot_start_args += ['--extra', arg]
        apppot_start_args += [ executable ] + arguments

        kw.setdefault('tags', dict())
        kw['tags'].append(apppot_tag)
        
        # init base class
        gc3libs.Application.__init__(
            self,
            'apppot-start.sh', # executable
            apppot_start_args, # arguments
            inputs, outputs, output_dir, **kw)

    @staticmethod
    def _add_to_inputs(inputs, localpath, remotepath):
        # XXX: Need to deal with the two possibilities for
        # initializing the `inputs` list.  Can this be simplified
        # by making `inputs` a writeable property of an
        # `Application` object?
        if isinstance(inputs, dict):
            inputs[localpath] = remotepath
        elif isinstance(inputs, list):
            inputs.append( (localpath, remotepath) )
        else:
            raise TypeError("Unexpected type for `inputs` parameter: need `dict` or `list`.")

    def xrsl(self, resource):
            # FIXME: for ARC submissions, replace `executable` with
            # the value of a (remotely defined) environment variable,
            # because otherwise ARC insists that 'apppot-start.sh'
            # should be included in "inputFiles", but it obviously
            # breaks all other submission schemes...
            original_executable = self.executable
            self.executable = '/$APPPOT_STARTUP'
            jobdesc = gc3libs.Application.xrsl(self, resource)
            self.executable = original_executable
            return jobdesc


## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(name="apppot",
                    optionflags=doctest.NORMALIZE_WHITESPACE)
