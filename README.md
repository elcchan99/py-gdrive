# py-gdrive

## Installation
```
pip install git+https://github.com/elcchan99/py-gdrive.git@master#egg=pygdrive
```

## Authentication

1) Go to APIs Console and make your own project.
1) Search for ‘Google Drive API’, select the entry, and click ‘Enable’.
1) Select ‘Credentials’ from the left menu, click ‘Create Credentials’, select ‘OAuth client ID’.
1) Now, the product name and consent screen need to be set -> click ‘Configure consent screen’ and follow the instructions. Once finished:
    1) Select ‘Application type’ to be Web application.
    1) Enter an appropriate name.
    1) Input http://localhost:8080 for ‘Authorized JavaScript origins’.
    1) Input http://localhost:8080/ for ‘Authorized redirect URIs’.
    1) Click ‘Save’.
1) Click ‘Download JSON’ on the right side of Client ID to download client_secret_<really long ID>.json.
1) rename the file to client_secret.json

## Sample Usage

```
from pygdrive.googledrive import *

auth = GoogleAuth()
drive = GoogleDrive(auth)

file = drive.find("my-folder")
print(file)

files = drive.list(file)
print(files)
```

## To Do

1) add tests
1) upload file, handle file replace case if match name
1) upload folder, handle file replace case if match name