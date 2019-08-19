from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import Resource
from enum import Enum
from collections import ChainMap
from typing import List, Dict, NamedTuple

import logging
logger = logging.getLogger(__name__)

DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/drive'
]

class GoogleAuth(object):
    __pickle_cache = ".token.pickle"
    service = None

    def __init__(self, credential_file: str='client_secret.json', scopes: List[str]=DEFAULT_SCOPES, save: bool=True):
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

        logger.info("logging in Google: /drive/api/v3")
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

class MimeType(Enum):
    FOLDER = 'application/vnd.google-apps.folder'

class GoogleDrive(object):
    LIST_LIMIT = 1000

    def __init__(self, auth: GoogleAuth):
        self.service = auth.service

    def __common_list(self, **kwargs) -> List[GoogleDriveFile]:
        args = dict(ChainMap({
            'fields': "files(id, name, mimeType, modifiedTime, capabilities)"
        }, kwargs))
        result = self.service.files().list(**args).execute()
        files = result.get('files', [])
        return GoogleDriveFile.construct(files)

    def find(self, name: str, mimeType: MimeType=None, parent: GoogleDriveFile=None) -> GoogleDriveFile:
        query = [f"name='{name}'"]
        if mimeType:
            query.append("mimeType='%s'" % mimeType.value)
        if parent:
            query.append("'%s' in parent s" % parent.id)
        result = self.__common_list(q=" and ".join(query), pageSize=1)
        logger.debug(f"result {result}")
        if len(result) < 1:
            return None
        logger.debug(f"folder {name}': {result[0]}")
        return result[0]

    def find_folder(self, name: str, parent: GoogleDriveFile=None) -> GoogleDriveFile:
        return self.find(name, MimeType.FOLDER, parent)

    def list(self, parent: GoogleDriveFile) -> List[GoogleDriveFile]:
        query = [f"'{parent.id}' in parents"]
        result = self.__common_list( q=" and ".join(query), pageSize=self.LIST_LIMIT)
        logger.debug(f"children of {parent.id}: {result}")
        return sorted(result, key=lambda x: x.name)

    def download(self, file: GoogleDriveFile, output):
        if type(output) is str:
            output_handler = open(output, 'wb')
        else:
            output_handler = output

        logger.info(f"download file[id={file.id}]: {file.name}")
        request = self.service.files().get_media(fileId=file.id)
        downloader = MediaIoBaseDownload(output_handler, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logger.info("\rdownloading %d%%.\r" % int(status.progress() * 100))
            output_handler.seek(0)