# -----------------------------------------------------------------------------
# Transport class (interface)
#

class Transport(object):

    def __init__(self):
        raise NotImplementedError("Abstract method `Transport()` called - this should have been defined in a derived class.")

    def connect(self):
        """
        Open an transport session.
        
        """
        raise NotImplementedError("Abstract method `Transport.open()` called - this should have been defined in a derived class.")

    def execute_command(self, command):
        """
        Execute a command using the available tranport media.  
        The command's input and output streams are returned 
        as python C{file}-like objects representing exit_status, stdout, stderr.

        @param command: the command to execute
        @type command: str
        @return: the exit_status, stdout, and stderr of the executing command
        @rtype: tuple(C{int}, L{ChannelFile}, L{ChannelFile})
       
        @raise TransportException: if fails to execute the command
        
        """
        raise NotImplementedError("Abstract method `Transport.execute_command()` called - this should have been defined in a derived class.")

    def listdir(self, path):
        """
        Return a list containing the names of the entries in the given C{path}.
        The list is in arbitrary order.  It does not include the special
        entries C{'.'} and C{'..'} even if they are present in the folder.
        This method is meant to mirror C{os.listdir} as closely as possible.
        
        @param path: path to list (defaults to C{'.'})
        @type path: str
        @return: list of filenames
        @rtype: list of str
        
        """
        raise NotImplementedError("Abstract method `Transport.listdir()` called - this should have been defined in a derived class.")

    def open(self, source, mode, bufsize=-1):
        """
        Open a file. The arguments are the same as for python's built-in C{file} 
        (aka C{open}).  A file-like object is returned, which closely mimics 
        the behavior of a normal python file object.
        
        @param source: name of the file to open
        @type source: str
        @param mode: mode (python-style) to open in
        @type mode: str
        @param bufsize: desired buffering (-1 = default buffer size)
        @type bufsize: int
        @return: a file object representing the open file
        @rtype: File
        
        @raise IOError: if the file could not be opened.        
        """
        raise NotImplementedError("Abstract method `Transport.open()` called - this should have been defined in a derived class.")

    def put(self, source, destinaton):
        """
        Copy the file source to the file or directory destination.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destinaton are path 
        names given as strings.
        Any exception raised by operations will be passed through.  
        
        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        raise NotImplementedError("Abstract method `Transport.put()` called - this should have been defined in a derived class.")

    def get(self, source, destinaton):
        """
        Copy the file source to the file or directory destinaton.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destination are path 
        names given as strings.
        Any exception raised by operations will be passed through.

        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        raise NotImplementedError("Abstract method `Transport.get()` called - this should have been defined in a derived class.")

    def remove(self, path):
        """
        Removes a file.
        """
        raise NotImplementedError("Abstract method `Transport.remove()` called - this should have been defined in a derived class.")

    def remove_tree(self, path):
        """
        Removes a directory tree.
        """
        raise NotImplementedError("Abstract method `Transport.remove_tree()` called - this should have been defined in a derived class.")

    def close(self):
        """
        Close the transport channel
        """
        raise NotImplementedError("Abstract method `Transport.close()` called - this should have been defined in a derived class.")


# -----------------------------------------------------------------------------
# SSH Transport class
#

import paramiko
import gc3libs.Default as Default
import gc3libs
import gc3libs.Exceptions as Exceptions
import sys

class SshTransport(Transport):

    ssh = None
    sftp = None
    _is_open = False

    def __init__(self, remote_frontend, port=Default.SSH_PORT, username=None):
        self.remote_frontend = remote_frontend
        self.port = port
        self.username = username

    def connect(self):
        """
        Open an transport session.
        
        """
        try:
            if not self._is_open:
                self.ssh = paramiko.SSHClient()
                self.ssh.load_system_host_keys()
                self.ssh.connect(self.remote_frontend,timeout=Default.SSH_CONNECT_TIMEOUT,username=self.username, allow_agent=True)
                self.sftp = self.ssh.open_sftp()
                self._is_open = True
                gc3libs.log.info("SshTransport remote_frontend: %s port: %d username: %s connection status [ conected ]" % (self.remote_frontend, self.port, self.username))
        except:
            gc3libs.log.error("Could not create ssh connection to %s" % host)
            raise Exceptions.TransportError("Failed while connecting to remote host: %s. Error type %s, %s"
                                            % (self.remote_frontend, sys.exc_info()[0], sys.exc_info()[1]))

    def execute_command(self, command):
        """
        Execute a command using the available tranport media.
        The command's input and output streams are returned
        as python C{file}-like objects representing exit_status, stdout, stderr.

        @param command: the command to execute
        @type command: str
        @return: the exit_status, stdout, and stderr of the executing command
        @rtype: tuple(C{int}, L{ChannelFile}, L{ChannelFile})
       
        @raise TransportException: if fails to execute the command
        
        """
        try:
            stdin_stream, stdout_stream, stderr_stream = self.ssh.exec_command(command)
            stdout = stdout_stream.read()
            stderr = stderr_stream.read()
            exitcode = stdout_stream.channel.recv_exit_status()
            gc3libs.log.info('execute_command: %s. exit status: %d' % (command, exitcode))
                
            return exitcode, stdout, stderr
        except:
            gc3libs.log.error('Failed while executing remote command: %s' % command)
            raise Exceptions.TransportError("Failed while executing remote command: %s. Error type %s, %s" 
                                            % (command, sys.exc_info()[0], sys.exc_info()[1]))
        
    def listdir(self, path):
        """
        Return a list containing the names of the entries in the given C{path}.
        The list is in arbitrary order.  It does not include the special
        entries C{'.'} and C{'..'} even if they are present in the folder.
        This method is meant to mirror C{os.listdir} as closely as possible.
        
        @param path: path to list (defaults to C{'.'})
        @type path: str
        @return: list of filenames
        @rtype: list of str
        
        """
        try:
            return self.sftp.listdir(path)
        except Exception, x:
            gc3libs.log.error("Failed method listdir. remote path: %s. remote host: %s." 
                              % (path, self.remote_frontend), exc_info=True)
            raise Exceptions.TransportError("Failed method listdir on %s. Error type %s, %s"
                                            % (path, sys.exc_info()[0], sys.exc_info()[1]))
        
    def put(self, source, destination):
        """
        Copy the file source to the file or directory destination.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destinaton are path 
        names given as strings.
        Any exception raised by operations will be passed through.  
        
        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        try:
            gc3libs.log.debug("Running metohd: put. local source: %s. remote destination: %s. remote host: %s." % (source, destination, self.remote_frontend))
            self.sftp.put(source, destination)
        except:
            gc3libs.log.error("Failed method put. local source: %s remote host: %s" % (source, self.remote_frontend))
            raise Exceptions.TransportError("Failed method put. Error type %s, %s"
                                            % (sys.exc_info()[0], sys.exc_info()[1]))

    def get(self, source, destination):
        """
        Copy the file source to the file or directory destinaton.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destination are path 
        names given as strings.
        Any exception raised by operations will be passed through.

        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        try:
            gc3libs.log.debug("Running method: get. remote source %s. remote host: %s. local destination/: %s" % (source, self.remote_frontend, destination))
            self.sftp.get(source, destination)
        except:
            gc3libs.log.error("Failed method get. remote source: %s remote host: %s local destination: %s" % (source, self.remote_frontend, destination))
            raise Exceptions.TransportError("Failed method get. Error type %s, %s"
                                            % (sys.exc_info()[0], sys.exc_info()[1]))

    def remove(self, path):
        """
        Removes a file.
        """
        try:
            gc3libs.log.debug("Running method: remove. path: %s. remote host: %s" % (path, self.remote_frontend))
            self.sftp.remove(path)
        except IOError, x:
            gc3libs.log.error("Failed method remove. remote file: %s remote host: %s" % (path, self.remote_frontend))
            raise Exceptions.TransportError("Failed method remove. Error type %s, %s"
                                            % (sys.exc_info()[0], sys.exc_info()[1]))
        
    def remove_tree(self, path):
        """
        Removes a directory tree.
        """
        try:
            gc3libs.log.debug("Running metohd: remove_tree. remote path: %s remote host: %s" % (path, self.remote_frontend))
            # Note: At the moment rmdir does not work as expected
            # self.sftp.rmdir(path)
            # easy workaround: use SSHClient to issue an rm -rf comamnd
            _command = "rm -rf '%s'" % path
            exit_code, stdout, stderr = self.execute_command(_command)
            if exit_code != 0:
                gc3libs.log.error("remote command %s failed with code %d. stdout: %s. stderr: %s" % (_command, exit_code, stdout, stderr))
                raise Exception("remote command %s failed with code %d. stdout: %s. stderr: %s" % (_command, exit_code, stdout, stderr))
        except:
            gc3libs.log.error("Failed metohd remove_tree. remote folder: %s remote host: %s" % (path, self.remote_frontend))
            raise Exceptions.TransportError("Failed method remove. Error type %s, %s"
                                            % (sys.exc_info()[0], sys.exc_info()[1]))

    def open(self, source, mode, bufsize=-1):
        try:
            return self.sftp.open(source, mode, bufsize)
        except:
            gc3libs.log.error("Failed method open. remote file: %s. remote host: %s" % (source, self.remote_frontend))
            raise Exceptions.TransportError("Failed method remove. Error type %s, %s"
                                            % (sys.exc_info()[0], sys.exc_info()[1]))
                       
    def close(self):
        """
        Close the transport channel
        """
        gc3libs.log.debug("Closing sftp and ssh connections... ")
        if self.sftp is not None:
            self.sftp.close()
        if self.ssh is not None:
            self.ssh.close()
        self._is_open = False
        gc3libs.log.info("SshTransport status [ closed ]")


import subprocess
import shlex
import shutil


# -----------------------------------------------------------------------------
# Local Transport class
#

class LocalTransport(Transport):

    _is_open = False

    def __init__(self):
        pass

    def open(self):
        """
        Open an transport session.        
        """
        self._is_open = True

    def execute_command(self, command):
        """
        Execute a command using the available tranport media.  
        The command's input and output streams are returned 
        as python C{file}-like objects representing exit_status, stdout, stderr.

        @param command: the command to execute
        @type command: str
        @return: the exit_status, stdout, and stderr of the executing command
        @rtype: tuple(C{int}, L{ChannelFile}, L{ChannelFile})
       
        @raise TransportException: if fails to execute the command
        
        """
        try:
            if self._is_open is False:
                raise Exception("Transport not open")

            subprocess_command = shlex.split(command)
            p = subprocess.Popen(subprocess_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)

            exitcode = p.comunicate()

            stdout = p.stdout.read()
            stderr = p.stderr.read()

            gc3libs.log.info('execute_command: %s. exit status: %d' % (command, exitcode))

            return exitcode, stdout, stderr

        except:
            gc3libs.log.error('Failed while executing command: %s' % command)
            raise TransportException("Failed while executing command: %s. Error type %s, %s" 
                                     % (command, sys.exc_info()[0], sys.exc_info()[1]))
        
    def listdir(self, path):
        """
        Return a list containing the names of the entries in the given C{path}.
        The list is in arbitrary order.  It does not include the special
        entries C{'.'} and C{'..'} even if they are present in the folder.
        This method is meant to mirror C{os.listdir} as closely as possible.
        
        @param path: path to list (defaults to C{'.'})
        @type path: str
        @return: list of filenames
        @rtype: list of str
        
        """
        try:
            if self._is_open is False:
                raise Exception("Transport not open")

            return os.listdir(path)

        except:
            gc3libs.log.error('Failed method listdir on %s' % path, exc_info=True)
            raise TransportException("Failed method listdir. path: %s. Error type %s, %s"
                                     % (path, sys.exc_info()[0], sys.exc_info()[1]))

    def put(self, source, destinaton):
        """
        Copy the file source to the file or directory destination.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destinaton are path 
        names given as strings.
        Any exception raised by operations will be passed through.  
        
        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        try:
            if self._is_open is False:
                raise Exception("Transport not open")

            gc3libs.log.debug("Running metohd: put. source: %s. destination: %s" % (source, destination))
            return shutil.copy(source, destination)
        except:
            gc3libs.log.critical("Failed method put. source: %s. destination: %s" % (source, destinaton))
            raise TransportException("Failed method put. source: %s destination: %s. Error type %s, %s"
                                     % (source, destination, sys.exc_info()[0], sys.exc_info()[1]))


    def get(self, source, destinaton):
        """
        Copy the file source to the file or directory destinaton.
        If destination is a directory, a file with the same basename 
        as source is created (or overwritten) in the directory specified. 
        Permission bits are copied. source and destination are path 
        names given as strings.
        Any exception raised by operations will be passed through.

        @param source: the file to copy
        @type source: str
        @param destinaton: the destination file or directory
        @type destinaton: str
        """
        gc3libs.log.debug("GET implemented with PUT... ")
        self.put(source,destination)

    def remove(self, path):
        """
        Removes a file.
        """
        try:
            if self._is_open is False:
                raise Exception("Transport not open")

            gc3libs.log.debug("Removing %s", path)
            return os.remove(path)
        except:
            gc3libs.log.critical("Failed while removing file %s " % path)
            raise TransportException("Failed while removing file %s. Error type %s, %s"
                                     % (path, sys.exc_info()[0], sys.exc_info()[1]))

    def remove_tree(self, path):
        """
        Removes a directory tree.
        """
        try:
            if self._is_open is False:
                raise Exception("Transport not open")

            gc3libs.log.debug("Running method: remove_tree. path: %s" % path)
            return os.removedirs(path)
        except:
            gc3libs.log.critical("Failed method remove_tree. path: %s" % path)
            raise TransportException("Failed while removing folder %s. Error type %s, %s"
                                     % (path, sys.exc_info()[0], sys.exc_info()[1]))

    def close(self):
        """
        Close the transport channel
        """
        self._is_open = False
        gc3libs.log.info("SshTransport status [ closed ]")

# -----------------------------------------------------------------------------
