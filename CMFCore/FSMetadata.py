""" Handles reading the properties for an object that comes from the filesystem.

$Id$
"""

from zLOG import LOG, ERROR
from sys import exc_info
from os.path import exists
from ConfigParser import ConfigParser

import re

class CMFConfigParser(ConfigParser):
    """ This our wrapper around ConfigParser to 
    solve a few minor niggles with the code """
    # adding in a space so that names can contain spaces
    OPTCRE = re.compile(
        r'(?P<option>[]\-[ \w_.*,(){}]+)'      # a lot of stuff found by IvL
        r'[ \t]*(?P<vi>[:=])[ \t]*'           # any number of space/tab,
                                              # followed by separator
                                              # (either : or =), followed
                                              # by any # space/tab
        r'(?P<value>.*)$'                     # everything up to eol
        )    

    def optionxform(self, optionstr):
        """ 
        Stop converting the key to lower case, very annoying for security etc 
        """
        return optionstr.strip()

class FSMetadata:
    # public API
    def __init__(self, filename):
        self._filename = filename

    def read(self):
        """ Find the files to read, either the old security and properties type or
        the new metadata type """
        filename = self._filename + '.metadata'
        if exists(filename):
            # found the new type, lets use that
            self._readMetadata()
        else:
            # not found so try the old ones
            self._properties = self._old_readProperties()
            self._security = self._old_readSecurity()

    def getSecurity(self):
        """ Gets the security settings """
        return self._security

    def getProperties(self):
        """ Gets the properties settings """
        return self._properties

    # private API
    def _readMetadata(self):
        """ Read the new file format using ConfigParser """
        cfg = CMFConfigParser()
        cfg.read(self._filename + '.metadata')

        # the two sections we care about
        self._properties = self._getSectionDict(cfg, 'default')
        self._security = self._getSectionDict(cfg, 'security', self._securityParser)
        # to add in a new value such as proxy roles,
        # just add in the section, call it using getSectionDict
        # if you need a special parser for some whacky
        # config, then just pass through a special parser
    
    def _nullParser(self, data):
        """ 
        This is the standard rather boring null parser that does very little 
        """
        return data
    
    def _securityParser(self, data):
        """ A specific parser for security lines 
        
        Security lines must be of the format
        
        (0|1):Role[,Role...]
        
        Where 0|1 is the acquire permission setting
        and Role is the roles for this permission
        eg: 1:Manager or 0:Manager,Anonymous
        """
        if data.find(':') < 1: 
            raise ValueError, "The security declaration is in the wrong format"
            
        acquire, roles = data.split(':')
        roles = [r.strip() for r in roles.split(',') if r.strip()]
        return (acquire, roles)

    def _getSectionDict(self, cfg, section, parser=None):
        """ 
        Get a section and put it into a dict, mostly a convenience
        function around the ConfigParser
        
        Note: the parser is a function to parse each value, so you can
        have custom values for the key value pairs 
        """
        if parser is None: 
            parser = self._nullParser

        props = {}
        if cfg.has_section(section):
            for opt in cfg.options(section):
                props[opt] = parser(cfg.get(section, opt))
            return props

        # we need to return None if we have none to be compatible
        # with existing API
        return None

    def _old_readProperties(self):
        """
        Reads the properties file next to an object.
        
        Moved from DirectoryView.py to here with only minor
        modifications. Old and deprecated in favour of .metadata now
        """
        fp = self._filename + '.properties'
        try:
            f = open(fp, 'rt')
        except IOError:
            return None
        else:
            lines = f.readlines()
            f.close()
            props = {}
            for line in lines:
                kv = line.split('=', 1)
                if len(kv) == 2:
                    props[kv[0].strip()] = kv[1].strip()
            return props
    
    def _old_readSecurity(self):
        """
        Reads the security file next to an object.
        
        Moved from DirectoryView.py to here with only minor
        modifications. Old and deprecated in favour of .metadata now
        """
        fp = self._filename + '.security'
        try:
            f = open(fp, 'rt')
        except IOError:
            return None        
        else:
            lines = f.readlines()
            f.close()
            prm = {}
            for line in lines:
                try:
                    c1 = line.index(':')+1
                    c2 = line.index(':',c1)
                    permission = line[:c1-1]
                    acquire = not not line[c1:c2] # get boolean                    
                    proles = line[c2+1:].split(',')
                    roles=[]
                    for role in proles:
                        role = role.strip()
                        if role:
                            roles.append(role)
                except:
                    LOG('DirectoryView',
                        ERROR,
                        'Error reading permission from .security file',
                        error=exc_info())
                        # warning use of exc_info is deprecated
                prm[permission]=(acquire,roles)
            return prm
