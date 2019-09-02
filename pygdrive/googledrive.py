from __future__ import print_function
import pickle
import os
from glob import glob
import magic
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.discovery import Resource
from enum import Enum
from collections import ChainMap
from datetime import datetime
from typing import List, Dict, NamedTuple, Tuple

import logging

DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/drive'
]

COMMON_FILE_FIELDS = 'id, name, mimeType, modifiedTime, capabilities'

def format_datetime(d: datetime) -> str:
    return d.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def file_mtime(file_path: str) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(file_path))

class GoogleAuth(object):
    __pickle_cache = ".token.pickle"
    service = None

    def __init__(self, credential_file: str='client_secret.json', scopes: List[str]=DEFAULT_SCOPES, save: bool=True):
        self.logger = logging.getLogger("%s.%s" % (__name__, "GoogleDrive"))
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(self.__pickle_cache):
            with open(self.__pickle_cache, 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credential_file, scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            if save:
                with open(self.__pickle_cache, 'wb') as token:
                    pickle.dump(creds, token)

        self.logger.info("logging in Google: /drive/api/v3")
        service = build('drive', 'v3', credentials=creds)
        self.service = service

class GoogleDriveFile(NamedTuple):
    id: str
    name:   str
    mimeType:   str
    modifiedTime:   str
    capabilities: Dict
    
    @classmethod
    def construct(cls, data):
        if isinstance(data,  list):
            return [cls.construct(d) for d in data]
        elif isinstance(data, dict):
            return cls(**data)
        else:
            raise ValueError("data must be either list of dictionary or dictionary")

    def isfile(self) -> bool:
        """Whether node is a File
        
        Returns:
            bool -- Result
        """
        return not self.isdir()

    def isdir(self) -> bool:
        """Whether node is a Folder
        
        Returns:
            bool -- Result
        """
        return self.mimeType == MimeType.FOLDER.value

class MimeType(Enum):
    FOLDER = 'application/vnd.google-apps.folder'
    SPREADSHEET = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

class GoogleDrive(object):
    LIST_LIMIT = 1000

    def __init__(self, auth: GoogleAuth):
        self.logger = logging.getLogger("%s.%s" % (__name__, "GoogleDrive"))
        self.service = auth.service
        self.mime = magic.Magic(mime=True)

    def __common_list(self, **kwargs) -> List[GoogleDriveFile]:
        args = dict(ChainMap({
            'fields': f"files({COMMON_FILE_FIELDS})"
        }, kwargs))
        result = self.service.files().list(**args).execute()
        files = result.get('files', [])
        return GoogleDriveFile.construct(files)

    def find(self, name: str, id: str=None, mimeType: MimeType=None, parent: GoogleDriveFile=None) -> GoogleDriveFile:
        """Find a single file in Google Drive
        
        Arguments:
            name {str} -- File exact name
        
        Keyword Arguments:
            id {str} -- ID of file (default: {None})
            mimeType {MimeType} -- Mime Type of file (default: {None})
            parent {GoogleDriveFile} -- Parent Folder (default: {None})
        
        Returns:
            GoogleDriveFile -- the GoogleDriveFile object, None if not found
        """
        query = [f"name='{name}'"]
        if id:
            query.append("id='%s'" % id)
        if mimeType:
            query.append("mimeType='%s'" % mimeType.value)
        if parent:
            query.append(f"'{parent.id}' in parents")
        result = self.__common_list(q=" and ".join(query), pageSize=1)
        self.logger.debug(f"result {result}")
        if len(result) < 1:
            return None
        self.logger.debug(f"folder {name}': {result[0]}")
        return result[0]

    def find_folder(self, name: str, id: str=None, parent: GoogleDriveFile=None) -> GoogleDriveFile:
        """Find a folder in Google Drive
        
        Arguments:
            name {str} -- Folder exact name
        
        Keyword Arguments:
            id {str} -- ID of file (default: {None})
            parent {GoogleDriveFile} -- Parent Folder (default: {None})
        
        Returns:
            GoogleDriveFile -- the GoogleDriveFile object, None if not found
        """
        return self.find(name, id, MimeType.FOLDER, parent)

    def list(self, parent: GoogleDriveFile) -> List[GoogleDriveFile]:
        """List files under a folder
        
        Arguments:
            parent {GoogleDriveFile} -- Parent Folder
        
        Returns:
            List[GoogleDriveFile] -- a list of GoogleDriveFile objects
        """
        query = [f"'{parent.id}' in parents"]
        result = self.__common_list( q=" and ".join(query), pageSize=self.LIST_LIMIT)
        self.logger.debug(f"children of {parent.id}: {result}")
        return sorted(result, key=lambda x: x.name)

    def download(self, file: GoogleDriveFile, output) -> Tuple[bool, str]:
        """Download single file
        
        Arguments:
            file {GoogleDriveFile} -- Target file in GoogleDrive to be downloaded
            output {[str|callable]} -- Output handler, str for local file, otherwise fileHandler 

        Returns:
            Tuple[bool, str] -- Result, Error report
        """
        if type(output) is str:
            output_handler = open(output, 'wb')
        else:
            output_handler = output

        try:
            self.logger.info(f"download file[id={file.id}]: {file.name}")
            request = self.service.files().get_media(fileId=file.id)
            downloader = MediaIoBaseDownload(output_handler, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                self.logger.info("\rdownloading %d%%.\r" % int(status.progress() * 100))
                output_handler.seek(0)
            return (True, None)
        except Exception as ex:
            self.logger.error(ex)
            return (False, str(ex))
            
    def download_folder(self, folder: GoogleDriveFile, output_path: str) -> Tuple[bool, Dict[str, str]]:
        """Download folder and its files
        
        Arguments:
            folder {GoogleDriveFile} -- Target folder in GoogleDrive to be downloaded
            output_path {str} -- local path
        
        Returns:
            Tuple[bool, Dict[str, str]] -- Result, Error report
        """
        errors = {}
        os.makedirs(output_path, exist_ok=True)
        for file in self.list(folder):
            p = os.path.join(output_path, file.name)
            try:
                if file.isdir():
                    r, err = self.download_folder(file, p)
                else:
                    r, err = self.download(file, p)
                if not r:
                    errors[file.id] = err
            except Exception as ex:
                self.logger.error(ex)
                errors[file.id] = str(ex)

        return (not errors, errors)

    def mkdir(self, name: str, parent: GoogleDriveFile=None) -> Tuple[GoogleDriveFile, str]:
        """Make directory
        
        Arguments:
            name {List[str]} -- folder name
        
        Keyword Arguments:
            parent {GoogleDriveFile} -- target folder, root folder if nothing (default: {None})
            depth {List[str]} -- depth path for logging (default: {[]})
        Returns:
            Tuple[GoogleDriveFile, str] -- GoogleDriveFile, error
        """
        try:
            file_metadata = {'name': name,
                             'mimeType' : MimeType.FOLDER.value}
            google_path = "name"
            if parent:
                file_metadata['parents'] = [parent.id]
                google_path = os.path.join(parent.name, name)
            self.logger.info("creating folder %s" % (google_path))
            file = self.service.files().create(body=file_metadata,
                                               media_body=None,
                                               fields=COMMON_FILE_FIELDS).execute()
            return (GoogleDriveFile.construct(file), None)
        except Exception as ex:
            self.logger.error(ex)
            return (None, str(ex))

    def upload(self, file_path:str, parent: GoogleDriveFile=None, recusive: bool=False, customMeta: Dict={}, depth: List[str]=[]) -> Tuple[GoogleDriveFile, str]:
        """Upload a file or folder to Google Drive
        
        Arguments:
            file_path {str} -- filepath of the file to be uploaded
        
        Keyword Arguments:
            parent {GoogleDriveFile} -- target folder, root folder if nothing (default: {None})
            recusive {bool} -- whether upload recusively (default: {False})
            customMeta {Dict} -- custom metadata overrides (default: {{}})
            depth {List[str]} -- depth path for logging (default: {[]})
        
        Returns:
            Tuple[List[str], str] -- List of uploaded GoogleDriveFile, error
        """
        try:
            if not os.path.exists(file_path):
                raise ValueError(f"filepath {file_path} not exists")

            isdir = os.path.isdir(file_path)
            file_name = os.path.basename(file_path)
            file_metadata = {'name': file_name,
                             'modifiedTime': format_datetime(file_mtime(file_path)) }
            if parent:
                file_metadata["parents"] = [parent.id]
            if isdir:
                file_metadata["mimeType"] = MimeType.FOLDER.value
            file_metadata.update(customMeta)
            
            new_depth = depth + [file_name]
            google_path = os.path.join(*new_depth)
            if isdir:
                self.logger.info("creating folder %s" % (google_path))
                media_body = None
            else:
                self.logger.info("uploading %s to %s" % (file_path, google_path))
                media_body = MediaFileUpload(file_path,
                                        mimetype=self.mime.from_file(file_path))
            file = self.service.files().create(body=file_metadata,
                                                media_body=media_body,
                                                fields=COMMON_FILE_FIELDS).execute()
            gfile = GoogleDriveFile.construct(file)
            res = [gfile]
            if recusive and isdir:
                for f in glob(os.path.join(file_path, "*")):
                    gfile_list, _ = self.upload(f, parent=gfile, recusive=recusive, depth=new_depth)
                    res = res + gfile_list
            return (res, None)
        except Exception as ex:
            self.logger.error(ex)
            return (None, str(ex))
