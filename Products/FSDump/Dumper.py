""" Classes: Dumper

$Id$
"""
import os

from AccessControl import ClassSecurityInfo
from App.special_dtml import DTMLFile
from App.Common import package_home
from AccessControl.class_init import InitializeClass
from OFS.SimpleItem import SimpleItem
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from ZODB.POSException import ConflictError

_wwwdir = os.path.join( package_home( globals() ), 'www' )

addDumperForm = PageTemplateFile( 'addDumper', _wwwdir )

USE_DUMPER_PERMISSION = 'Use Dumper'

def addDumper( self, id, fspath=None, use_metadata_file=0, REQUEST=None ):
    """
    """
    dumper = Dumper()
    dumper.id = id
    dumper.edit( fspath, use_metadata_file )
    self._setObject( id, dumper )

    if REQUEST is not None:
        REQUEST[ 'RESPONSE' ].redirect( 'manage_main' )

class Dumper( SimpleItem ):
    """
    """
    meta_type = 'Dumper'

    manage_options = ( { 'label'    : 'Edit'
                       , 'action'   : 'editForm'
                       , 'help'     : ('FSDump' ,'Dumper_editForm.stx')
                       }
                     , { 'label'    : 'Security'
                       , 'action'   : 'manage_access'
                       , 'help'     : ('OFSP','Security_Define-Permissions.stx')
                       }
                     )

    security = ClassSecurityInfo()
    
    fspath = None
    use_metadata_file = 0

    #
    #   Management interface methods.
    #
    index_html = None

    security.declareProtected( USE_DUMPER_PERMISSION, 'editForm' )
    editForm = PageTemplateFile( 'editDumper', _wwwdir )

    security.declareProtected( USE_DUMPER_PERMISSION, 'edit' )
    def edit( self, fspath, use_metadata_file, REQUEST=None ):
        """
            Update the path to which we will dump our peers.
        """
        self._setFSPath( fspath )
        self.use_metadata_file = use_metadata_file

        if REQUEST is not None:
            REQUEST['RESPONSE'].redirect( self.absolute_url()
                                        + '/editForm'
                                        + '?manage_tabs_message=Dumper+updated.'
                                        )

    security.declareProtected( USE_DUMPER_PERMISSION, 'dumpToFS' )
    def dumpToFS( self, REQUEST=None ):
        """
            Iterate recursively over our peers, creating simulacra
            of them on the filesystem in 'fspath'
        """
        if REQUEST and REQUEST.form.has_key( 'fspath' ):
            self._setFSPath( REQUEST.form[ 'fspath' ] )

        parent = self.aq_parent.aq_base
        if getattr(parent, 'isTopLevelPrincipiaApplicationObject', 0):
            self._dumpRoot( self.aq_parent )
        else:
            self._dumpFolder( self.aq_parent )

        if REQUEST is not None:
            REQUEST['RESPONSE'].redirect( self.absolute_url()
                                        + '/editForm'
                                        + '?manage_tabs_message=Peers+dumped.'
                                        )
 
    #
    #   Utility methods
    #
    security.declarePrivate( '_setFSPath' )
    def _setFSPath( self, fspath ):
        #   Canonicalize fspath.
        fspath = os.path.normpath( fspath )
        if not os.path.isabs( fspath ):
            raise "Dumper Error", "Path must be absolute."
        self.fspath = fspath

    security.declarePrivate( '_buildPathString' )
    def _buildPathString( self, path=None ):
        #   Construct a path string, relative to self.fspath.
        if self.fspath is None:
           raise "Dumper Error", "Path not set."

        if path is None:
            path = self.fspath
        else:
            path = os.path.normpath( os.path.join( self.fspath, path ) )
        
        return path

    security.declarePrivate( '_checkFSPath' )
    def _checkFSPath( self, path=None ):
        #   Ensure that fspath/path exists.
        path = self._buildPathString( path )

        if not os.path.exists( path ):
            os.makedirs( path )
        
        return path

    security.declarePrivate( '_createFile' )
    def _createFile( self, path, filename, mode='w' ):
        #   Create/replace file;  return the file object.
        fullpath = "%s/%s" % ( self._checkFSPath( path ), filename )
        return open( fullpath, mode )

    security.declarePrivate( '_createMetadataFile' )
    def _createMetadataFile( self, path, filename, mode='w' ):
        #   Create/replace file;  return the file object.
        extension = self.use_metadata_file and 'metadata' or 'properties'
        fullpath = "%s/%s.%s" % ( self._checkFSPath( path )
                                , filename, extension )
        file = open( fullpath, mode )
        if self.use_metadata_file:
            print >> file, "[default]"
        else:
            print >> file, "[Default]"
        return file
    
    security.declarePrivate( '_dumpObject' )
    def _dumpObject( self, object, path=None ):
        #   Dump one item, using path as prefix.
        try:
            handler = self._handlers.get( object.meta_type, None )
            if handler is not None:
                handler( self, object, path )
                return 1
        except ConflictError:
            raise
        except:
            return -1
        return 0
            

    security.declarePrivate( '_dumpObjects' )
    def _dumpObjects( self, objects, path=None ):
        #   Dump each item, using path as prefix.
        dumped = []
        for object in objects:
            if self._dumpObject( object, path ) > 0:
                id = object.id
                if callable( id ):
                    id = id()
                dumped.append( ( id, object.meta_type ) )
        return dumped


    security.declarePrivate( '_writeProperties' )
    def _writeProperties( self, obj, file ):
        propIDs = obj.propertyIds()
        propIDs.sort()  # help diff out :)
        for propID in propIDs:
            type = obj.getPropertyType( propID )
            value = obj.getProperty( propID )
            if self.use_metadata_file and type=='string':
                file.write( '%s=%s\n' % ( propID, value ) )
            else:
                file.write( '%s:%s=%s\n' % ( propID, type, value ) )

    #
    #   Type-specific dumpers
    #
    security.declarePrivate( '_dumpRoot' )
    def _dumpRoot( self, obj ):
        self._dumpObjects( obj.objectValues() )

    security.declarePrivate( '_dumpFolder' )
    def _dumpFolder( self, obj, path=None ):
        #   Recurse to dump items in a folder.
        if path is None:
            path = ''
        path = os.path.join( path, obj.id )
        file = self._createMetadataFile( path, '' )
        self._writeProperties( obj, file )
        dumped = self._dumpObjects( obj.objectValues(), path )
        dumped.sort() # help diff out :)

        if self.use_metadata_file:
            print >> file, "\n[Objects]"
        else:
            file.close()
            file = self._createFile( path, '.objects' )

        for id, meta in dumped:
            file.write( '%s:%s\n' % ( id, meta ) )
        file.close()

    security.declarePrivate( '_dumpDTML' )
    def _dumpDTML( self, obj, path=None, suffix='dtml' ):
        #   Dump obj (assumed to be a DTML Method/Document) to the
        #   filesystem as a file, appending 'suffix' to the name.
        peer_id = obj.id()
        file = self._createFile( path, '%s.%s' % ( peer_id, suffix ) )
        text = obj.raw
        if text[-1] != '\n':
            text = '%s\n' % text
        file.write( text )
        file.close()

    security.declarePrivate( '_dumpSecurityInfo' )
    def _dumpSecurityInfo(self, obj, file):
        if getattr(obj.aq_base, '_proxy_roles', None):
            file.write('proxy=%s\n' % ','.join(obj._proxy_roles))
        security_header_written = 0
        valid_roles = obj.valid_roles()
        for perm_dict in obj.permission_settings():
            perm_name = perm_dict['name']
            acquire = (perm_dict['acquire'] and 1) or 0
            roles = []
            for role_idx in range(len(valid_roles)):
                if perm_dict['roles'][role_idx]['checked']:
                    roles.append(valid_roles[role_idx])
            if roles or (acquire==0):
                if not security_header_written:
                    security_header_written = 1
                    file.write('\n[security]\n')
                file.write('%s=%d:%s\n' % (perm_name, acquire, ','.join(roles)))

    security.declarePrivate( '_dumpDTMLMethod' )
    def _dumpDTMLMethod( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a DTML Method) to the
        #   filesystem as a file, with the accompanyting properties file.
        self._dumpDTML( obj, path )
        file = self._createMetadataFile( path, '%s.dtml' % obj.id() )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            self._dumpSecurityInfo(obj, file)
        else:
            file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpZWikiPage' )
    def _dumpZWikiPage( self, obj, path=None, suffix='zwiki' ):
        peer_id = obj.id()
        file = self._createFile( path, '%s.%s' % ( peer_id, suffix ) )
        text = obj.text()
        if text[-1] != '\n':
            text = '%s\n' % text
        file.write( text )
        file.close()

        if self.use_metadata_file:
            file = self._createMetadataFile( path, '%s.%s' % ( peer_id,suffix))
            self._writeProperties( obj, file )
            self._dumpSecurityInfo(obj, file)
            file.close()

    security.declarePrivate( '_dumpDTMLDocument' )
    def _dumpDTMLDocument( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a DTML Document) to the
        #   filesystem as a file, with the accompanyting properties file.
        self._dumpDTML( obj, path )
        file = self._createMetadataFile( path, '%s.dtml' % obj.id() )
        self._writeProperties( obj, file )
        file.close()

    security.declarePrivate( '_dumpExternalMethod' )
    def _dumpExternalMethod( self, obj, path=None ):
        #   Dump properties of obj (assumed to be an Externa Method) to the
        #   filesystem as a file.
        file = self._createMetadataFile( path, '%s.em' % obj.id )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            file.write( 'module=%s\n' % obj._module )
            file.write( 'function=%s\n' % obj._function )
            self._dumpSecurityInfo(obj, file)
        else:
            file.write( 'title:string=%s\n' % obj.title )
            file.write( 'module:string=%s\n' % obj._module )
            file.write( 'function:string=%s\n' % obj._function )
        file.close()

    security.declarePrivate( '_dumpFileOrImage' )
    def _dumpFileOrImage( self, obj, path=None ):
        #   Dump properties of obj (assumed to be an Externa Method) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createMetadataFile( path, '%s' % obj.id() )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            file.write( 'content_type=%s\n' % obj.content_type )
            file.write( 'precondition=%s\n' % obj.precondition )
        else:
            file.write( 'title:string=%s\n' % obj.title )
            file.write( 'content_type:string=%s\n' % obj.content_type )
            file.write( 'precondition:string=%s\n' % obj.precondition )
        file.close()
        file = self._createFile( path, obj.id(), 'wb' )
        data = obj.data
        if type( data ) == type( '' ):
            file.write( data )
        else:
            while data is not None:
                file.write( data.data )
                data = data.next
        file.close()

    security.declarePrivate( '_dumpPythonMethod' )
    def _dumpPythonMethod( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Python Method) to the
        #   filesystem as a file, with the accompanyting properties file.
        body_lines = obj._body.split( '\n' )
        body = '\n    '.join( body_lines ) 
        text = "def %s(%s)\n\n    %s" % ( obj.id, obj._params, body )
        if text[-1] != '\n':
            text = '%s\n' % text
        file = self._createFile( path, '%s.py' % obj.id )
        file.write( text )
        file.close()
        file = self._createMetadataFile( path, '%s.py' % obj.id )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            self._dumpSecurityInfo(obj, file)
        else:
            file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpPythonScript' )
    def _dumpPythonScript( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Python Script) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.py' % obj.id )
        file.write( obj.read() )
        file.close()
        file = self._createMetadataFile( path, '%s.py' % obj.id )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            self._dumpSecurityInfo(obj, file)
        else:
            file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpControllerPythonScript' )
    def _dumpControllerPythonScript( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Python Script) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.cpy' % obj.id )
        file.write( obj.read() )
        file.close()
        file = self._createMetadataFile( path, '%s.cpy' % obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpValidatorScript' )
    def _dumpValidatorScript( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Controller Validator) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.vpy' % obj.id )
        file.write( obj.read() )
        file.close()
        file = self._createMetadataFile( path, '%s.vpy' % obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpControllerPageTemplate' )
    def _dumpControllerPageTemplate( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a ZopeControllerPageTemplate) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.cpt' % obj.id )
        file.write( obj.read() )
        file.close()
        file = self._createMetadataFile( path, '%s.cpt' % obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpPageTemplate' )
    def _dumpPageTemplate( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a ZopePageTemplate) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.pt' % obj.id )
        file.write( obj.read() )
        file.close()
        file = self._createMetadataFile( path, '%s.pt' % obj.id )
        if self.use_metadata_file:
            file.write( 'title=%s\n' % obj.title )
            self._dumpSecurityInfo(obj, file)
        else:
            file.write( 'title:string=%s\n' % obj.title )
        file.close()

    security.declarePrivate( '_dumpSQLMethod' )
    def _dumpSQLMethod( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a SQL Method) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.zsql' % obj.id )
        text = "%s" % obj.src
        file.write(' <dtml-comment>\n')
        file.write( 'title:%s\n' % obj.title )
        file.write( 'arguments: %s\n'
                     % ' '.join(obj.arguments_src.splitlines() ) )
        file.write( 'connection_id:%s\n' % obj.connection_id )
        file.write( 'max_rows:%s\n' % obj.max_rows_ )
        file.write( 'max_cache:%s\n' % obj.max_cache_ )
        file.write( 'cache_time:%s\n' % obj.cache_time_ )
        file.write( 'class_name:%s\n' % obj.class_name_ )
        file.write( 'class_file:%s\n' % obj.class_file_ )
        file.write( '</dtml-comment>\n')
        if text[-1] != '\n':
            text = '%s\n' % text
        file.write( text )
        file.close()

    security.declarePrivate( '_dumpZCatalog' )
    def _dumpZCatalog( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a ZCatalog) to the
        #   filesystem as a file, with the accompanyting properties file.
        file = self._createFile( path, '%s.catalog' % obj.id )
        for brain in obj.searchResults():
            file.write( '%s\n' % obj.getpath( brain.data_record_id_ ) )
        file.close()
        file = self._createMetadataFile( path, '%s' % obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.write( 'vocab_id:string=%s\n' % obj.vocab_id )
        file.write( 'threshold:int=%s\n' % obj.threshold )
        file.close()
        file = self._createFile( path, '%s.indexes' % obj.id )
        for index in obj.index_objects():
            file.write( '%s:%s\n' % ( index.id, index.meta_type ) )
        file.close()
        file = self._createFile( path, '%s.metadata' % obj.id )
        for column in obj.schema():
            file.write( '%s\n' % column )
        file.close()
    
    security.declarePrivate( '_dumpZClass' )
    def _dumpZClass( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a ZClass) to the
        #   filesystem as a directory, including propertysheets and
        #   methods, as well as any nested ZClasses.
        if path is None:
            path = ''
        path = os.path.join( path, obj.id )
        file = self._createMetadataFile( path, '' )
        file.write( 'title:string=%s\n' % obj.title )
        file.write( 'metatype:string=%s\n' % obj._zclass_.meta_type )
        file.write( 'bases:tokens=%s\n'
                  % ','.join( map( lambda klass: str(klass), obj._zbases ) )
                  )
        file.write( 'class_id:int=%s\n' % obj._zclass_.__module__ )
        file.close()

        #   Dump icon
        file = self._createFile( path, '.icon', 'wb' )
        img = obj._zclass_.ziconImage
        data = img.data
        if type( data ) == type( '' ):
            file.write( data )
        else:
            while data is not None:
                file.write( data.data )
                data = data.next
        file.close()

        #   Dump views
        file = self._createFile( path, '.views' )
        for view in obj.propertysheets.views.data():
            file.write( '%s:%s\n' % ( view[ 'label' ], view[ 'action' ] ) )
        file.close()

        #   Dump property sheets.
        sheetpath = os.path.join( path, 'propertysheets' , 'common' )
        sheets = self._dumpObjects( obj.propertysheets.common.objectValues()
                                  , sheetpath )
        sheets.sort() # help diff out :)
        file = self._createFile( sheetpath, '.objects' )
        for id, meta in sheets:
            file.write( '%s:%s\n' % ( id, meta ) )
        file.close()

        #   Dump methods
        methodpath = os.path.join( path, 'propertysheets', 'methods' )
        methods = self._dumpObjects( obj.propertysheets.methods.objectValues()
                                   , methodpath )
        methods.sort() # help diff out :)
        file = self._createFile( methodpath, '.objects' )
        for id, meta in methods:
            file.write( '%s:%s\n' % ( id, meta ) )
        file.close()
    
    security.declarePrivate( '_dumpZClassPropertySheet' )
    def _dumpZClassPropertySheet( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a ZClass) to the
        #   filesystem as a directory, including propertysheets and
        #   methods, as well as any nested ZClasses.
        file = self._createFile( path, obj.id )
        self._writeProperties( obj, file )
        file.close()

        file = self._createMetadataFile( path, obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.close()
    
    security.declarePrivate( '_dumpPermission' )
    def _dumpPermission( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Zope Permission) to the
        #   filesystem as a .properties file.
        file = self._createMetadataFile( path, obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.write( 'name:string=%s\n' % obj.name )
        file.close()

    security.declarePrivate( '_dumpFactory' )
    def _dumpFactory( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Zope Factory) to the
        #   filesystem as a .properties file.
        file = self._createMetadataFile( path, obj.id )
        file.write( 'title:string=%s\n' % obj.title )
        file.write( 'object_type:string=%s\n' % obj.object_type )
        file.write( 'initial:string=%s\n' % obj.initial )
        file.write( 'permission:string=%s\n' % obj.permission )
        file.close()

    security.declarePrivate( '_dumpWizard' )
    def _dumpWizard( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a Wizard) to the
        #   filesystem as a directory, containing a .properties file
        #   and analogues for the pages.
        if path is None:
            path = ''
        path = os.path.join( path, obj.id )
        file = self._createMetadataFile( path, '' )
        file.write( 'title:string=%s\n' % obj.title )
        file.write( 'description:text=[[%s]]\n' % obj.description )
        file.write( 'wizard_action:string=%s\n' % obj.wizard_action )
        file.write( 'wizard_icon:string=%s\n' % obj.wizard_icon )
        file.write( 'wizard_hide_title:int=%s\n' % obj.wizard_hide_title )
        file.write( 'wizard_stepcount:int=%s\n' % obj.wizard_stepcount )
        file.close()

        pages = self._dumpObjects( obj.objectValues(), path )

        pages.sort() # help diff out :)
        file = self._createFile( path, '.objects' )
        for id, meta in pages:
            file.write( '%s:%s\n' % ( id, meta ) )
        file.close()

    security.declarePrivate( '_dumpWizardPage' )
    def _dumpWizardPage( self, obj, path=None ):
        #   Dump properties of obj (assumed to be a WizardPage) to the
        #   filesystem as a file, appending ".wizardpage" to the name.
        self._dumpDTML( obj, path, 'wizardpage' )
        file = self._createMetadataFile( path, obj.id() )
        self._writeProperties( obj, file )
        file.close()

    security.declarePrivate( '_dumpFormulatorForm' )
    def _dumpFormulatorForm( self, obj, path=None ):
        if path is None:
            path = ''
        file = self._createFile(path, obj.id + '.form')
        file.write(obj.get_xml())
        file.close()

    _handlers = { 'DTML Method'     : _dumpDTMLMethod
                , 'DTML Document'   : _dumpDTMLDocument
                , 'Folder'          : _dumpFolder
                , 'BTreeFolder2'    : _dumpFolder
                , 'External Method' : _dumpExternalMethod
                , 'File'            : _dumpFileOrImage
                , 'Image'           : _dumpFileOrImage
                , 'Python Method'   : _dumpPythonMethod
                , 'Script (Python)' : _dumpPythonScript
                , 'Controller Python Script' : _dumpControllerPythonScript
                , 'Controller Validator' : _dumpValidatorScript
                , 'Controller Page Template' : _dumpControllerPageTemplate
                , 'Page Template'   : _dumpPageTemplate
                , 'Z SQL Method'    : _dumpSQLMethod
                , 'ZCatalog'        : _dumpZCatalog
                , 'Z Class'         : _dumpZClass
                , 'Common Instance Property Sheet'
                                    : _dumpZClassPropertySheet
                , 'Zope Permission' : _dumpPermission
                , 'Zope Factory'    : _dumpFactory
                , 'Wizard'          : _dumpWizard
                , 'Wizard Page'     : _dumpWizardPage
                , 'Formulator Form' : _dumpFormulatorForm
               #, 'SQL DB Conn'     : _dumpDBConn
                , 'ZWiki Page'      : _dumpZWikiPage
                }

    security.declareProtected( USE_DUMPER_PERMISSION, 'testDump' )
    def testDump( self, peer_path, path=None, REQUEST=None ):
        """
            Test dumping a single item.
        """
        obj = self.aq_parent.restrictedTraverse( peer_path )
        self._dumpObject( obj )
        if REQUEST is not None:
            REQUEST['RESPONSE'].redirect( self.absolute_url()
                                        + '/editForm'
                                        + '?manage_tabs_message=%s+dumped.'
                                        % peer_path
                                        )

InitializeClass( Dumper )

