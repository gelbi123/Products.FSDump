##############################################################################
#
# Copyright (c) 2001 Zope Corporation and Contributors. All Rights Reserved.
# 
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
# 
##############################################################################

"""Basic member data tool.
$Id$
"""
__version__='$Revision$'[11:-2]

import string
from utils import UniqueObject, getToolByName, _dtmldir
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from Globals import Acquisition, Persistent, DTMLFile
import Globals
from AccessControl.Role import RoleManager
from BTrees.OOBTree import OOBTree
from ZPublisher.Converters import type_converters
from Acquisition import aq_inner, aq_parent, aq_base
from AccessControl import ClassSecurityInfo
from CMFCorePermissions import ViewManagementScreens
import CMFCorePermissions
from ActionProviderBase import ActionProviderBase

_marker = []  # Create a new marker object.


class MemberDataTool (UniqueObject, SimpleItem, PropertyManager, ActionProviderBase):
    '''This tool wraps user objects, making them act as Member objects.
    '''
    id = 'portal_memberdata'
    meta_type = 'CMF Member Data Tool'
    _actions = []
    _v_temps = None
    _properties = ()

    security = ClassSecurityInfo()

    manage_options=( ActionProviderBase.manage_options +
                     ({ 'label' : 'Overview'
                       , 'action' : 'manage_overview'
                       }
                     , { 'label' : 'Contents'
                       , 'action' : 'manage_showContents'
                       }
                     )
                   + PropertyManager.manage_options
                   + SimpleItem.manage_options
                   )

    #
    #   ZMI methods
    #
    security.declareProtected( CMFCorePermissions.ManagePortal
                             , 'manage_overview' )
    manage_overview = DTMLFile( 'explainMemberDataTool', _dtmldir )

    security.declareProtected( CMFCorePermissions.ViewManagementScreens
                             , 'manage_showContents')
    manage_showContents = DTMLFile('memberdataContents', _dtmldir )

    security.declareProtected( CMFCorePermissions.ViewManagementScreens
                             , 'getContentsInformation',)


    def __init__(self):
        self._members = OOBTree()
        # Create the default properties.
        self._setProperty('email', '', 'string')
        self._setProperty('portal_skin', '', 'string')
        self._setProperty('listed', '', 'boolean')
        self._setProperty('login_time', '2000/01/01', 'date')
        self._setProperty('last_login_time', '2000/01/01', 'date')

    #
    #   'portal_memberdata' interface methods
    #
    security.declarePrivate('listActions')
    def listActions(self, info=None):
        """
        Return actions provided via tool.
        """
        return self._actions

    security.declarePrivate('getMemberDataContents')
    def getMemberDataContents(self):
        '''
        Return the number of members stored in the _members
        BTree and some other useful info
        '''
        membertool   = getToolByName(self, 'portal_membership')
        members      = self._members
        user_list    = membertool.listMemberIds()
        member_list  = members.keys()
        member_count = len(members)
        orphan_count = 0

        for member in member_list:
            if member not in user_list:
                orphan_count = orphan_count + 1

        return [{ 'member_count' : member_count,
                  'orphan_count' : orphan_count }]

    security.declarePrivate( 'searchMemberDataContents' )
    def searchMemberDataContents( self, search_param, search_term ):
        """ Search members """
        res = []

        if search_param == 'username':
            search_param = 'id'

        for user_wrapper in self._members.values():
            searched = getattr( user_wrapper, search_param, None )
            if searched is not None and string.find( searched, search_term ) != -1:
                res.append( { 'username' : getattr( user_wrapper, 'id' )
                            , 'email' : getattr( user_wrapper, 'email', '' )
                            }
                          )

        return res

    security.declarePrivate('pruneMemberDataContents')
    def pruneMemberDataContents(self):
        '''
        Compare the user IDs stored in the member data
        tool with the list in the actual underlying acl_users
        and delete anything not in acl_users
        '''
        membertool= getToolByName(self, 'portal_membership')
        members   = self._members
        user_list = membertool.listMemberIds()

        for tuple in members.items():
            member_name = tuple[0]
            member_obj  = tuple[1]
            if member_name not in user_list:
                del members[member_name]

    security.declarePrivate('wrapUser')
    def wrapUser(self, u):
        '''
        If possible, returns the Member object that corresponds
        to the given User object.
        '''
        id = u.getUserName()
        members = self._members
        if not members.has_key(id):
            # Get a temporary member that might be
            # registered later via registerMemberData().
            temps = self._v_temps
            if temps is not None and temps.has_key(id):
                m = temps[id]
            else:
                base = aq_base(self)
                m = MemberData(base, id)
                if temps is None:
                    self._v_temps = {id:m}
                else:
                    temps[id] = m
        else:
            m = members[id]
        # Return a wrapper with self as containment and
        # the user as context.
        return m.__of__(self).__of__(u)

    security.declarePrivate('registerMemberData')
    def registerMemberData(self, m, id):
        '''
        Adds the given member data to the _members dict.
        This is done as late as possible to avoid side effect
        transactions and to reduce the necessary number of
        entries.
        '''
        self._members[id] = m

Globals.InitializeClass(MemberDataTool)


class MemberData (SimpleItem):
    security = ClassSecurityInfo()

    def __init__(self, tool, id):
        self.id = id
        # Make a temporary reference to the tool.
        # The reference will be removed by notifyModified().
        self._tool = tool

    security.declarePrivate('notifyModified')
    def notifyModified(self):
        # Links self to parent for full persistence.
        tool = getattr(self, '_tool', None)
        if tool is not None:
            del self._tool
            tool.registerMemberData(self, self.getId())

    security.declarePublic('getUser')
    def getUser(self):
        # The user object is our context, but it's possible for
        # restricted code to strip context while retaining
        # containment.  Therefore we need a simple security check.
        parent = aq_parent(self)
        bcontext = aq_base(parent)
        bcontainer = aq_base(aq_parent(aq_inner(self)))
        if bcontext is bcontainer or not hasattr(bcontext, 'getUserName'):
            raise 'MemberDataError', "Can't find user data"
        # Return the user object, which is our context.
        return parent

    def getTool(self):
        return aq_parent(aq_inner(self))

    security.declarePublic('getMemberId')
    def getMemberId(self):
        return self.getUser().getUserName()

    security.declarePrivate('setMemberProperties')
    def setMemberProperties(self, mapping):
        '''Sets the properties of the member.
        '''
        # Sets the properties given in the MemberDataTool.
        tool = self.getTool()
        for id in tool.propertyIds():
            if mapping.has_key(id):
                if not self.__class__.__dict__.has_key(id):
                    value = mapping[id]
                    if type(value)==type(''):
                        proptype = tool.getPropertyType(id) or 'string'
                        if type_converters.has_key(proptype):
                            value = type_converters[proptype](value)
                    setattr(self, id, value)
        # Hopefully we can later make notifyModified() implicit.
        self.notifyModified()

    security.declarePublic('getProperty')
    def getProperty(self, id, default=_marker):

        tool = self.getTool()
        base = aq_base( self )

        # First, check the wrapper (w/o acquisition).
        # XXX: s.b., tool.getPropertyForMember( self, id, default )?
        value = getattr( base, id, _marker )
        if value is not _marker:
            return value

        # Then, check the tool for a value other than ''
        tool_value = tool.getProperty( id, _marker )
        user_value = getattr( self.getUser(), id, default )
        
        if tool_value is not _marker:
            if not tool_value and not user_value:
                value = tool_value
            elif not tool_value and user_value:
                value = user_value
        else:
            if user_value:
                value = user_value
            else:
                raise 'Property not found', id

        return value

    security.declarePrivate('getPassword')
    def getPassword(self):
        """Return the password of the user."""
        return self.getUser()._getPassword()

    security.declarePrivate('setSecurityProfile')
    def setSecurityProfile(self, password=None, roles=None, domains=None):
        """Set the user's basic security profile"""
        u = self.getUser()
        # This is really hackish.  The Zope User API needs methods
        # for performing these functions.
        if password is not None:
            u.__ = password
        if roles is not None:
            u.roles = roles
        if domains is not None:
            u.domains = domains

    def __str__(self):
        return self.getMemberId()

    ### User object interface ###

    security.declarePublic('getUserName')
    def getUserName(self):
        """Return the username of a user"""
        return self.getUser().getUserName()

    security.declarePublic('getId')
    def getId(self):
        """Get the ID of the user. The ID can be used, at least from
        Python, to get the user from the user's
        UserDatabase"""
        return self.getUser().getId()

    security.declarePublic('getRoles')
    def getRoles(self):
        """Return the list of roles assigned to a user."""
        return self.getUser().getRoles()

    security.declarePublic('getRolesInContext')
    def getRolesInContext(self, object):
        """Return the list of roles assigned to the user,
           including local roles assigned in context of
           the passed in object."""
        return self.getUser().getRolesInContext(object)

    security.declarePublic('getDomains')
    def getDomains(self):
        """Return the list of domain restrictions for a user"""
        return self.getUser().getDomains()

    security.declarePublic('has_role')
    def has_role(self, roles, object=None):
        """Check to see if a user has a given role or roles."""
        return self.getUser().has_role(roles, object)

    # There are other parts of the interface but they are
    # deprecated for use with CMF applications.

Globals.InitializeClass(MemberData)
