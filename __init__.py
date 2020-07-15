import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json
import base64
import time, random, hashlib

class RegistryError(ValueError):
    pass

class GISS:
    def get_service(self,SCOPES,path): # Get Docs API service - Docs Quickstart
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('docs', 'v1', credentials=creds), build('drive', 'v3', credentials=creds)

    def __init__(self,folderId,scopes=['https://www.googleapis.com/auth/drive'],path='credentials.json'):
        self.docs, self.drive = self.get_service(scopes,path)
        self.folder = folderId
        self._check()

    def _get_lines(self,docId):
        doc = self.docs.documents().get(documentId=docId).execute()
        lines = [i['paragraph']['elements'][0]['textRun']['content'].strip() for i in doc['body']['content'][1:]]
        leng = sum([len(i['paragraph']['elements'][0]['textRun']['content']) for i in doc['body']['content'][1:]])
        return lines, leng
        
    
    def _check(self): # Perform initial check
        current_files = self._list()
        if len(current_files) > 0:
            has_registry = False
            for f in current_files:
                if f['name'] == '._registry':
                    has_registry = True
                    self.registry = {}
                    self.reg_id = f['id']
                    lines, self.reg_len = self._get_lines(f['id'])
                    for l in lines:
                        if l.endswith('}}'):
                            l = l[:len(l)-1]
                        if '=' in l:
                            self.registry[l.split('=')[0]] = json.loads(l.split('=')[1])
                    self._write_reg()
                    break
            if not has_registry:
                raise RegistryError('Cannot find ._registry in this folder. Any files in this folder are unlinked and lost.')
            else:
                #print('Found ._registry')
                pass
        else:
            print('New folder detected. Creating ._registry. Do not delete this file.')
            body = {
                'name':'._registry',
                'mimeType':'application/vnd.google-apps.document',
                'parents':[self.folder]
            }
            f = self.drive.files().create(body=body).execute()
            self.reg_id = f['id']
            self.reg_len = 0
            self.registry = {
                '._reserved_persistent':{
                    'all':[]
                }
            }
            self._write_reg()
    
    def _list(self):
        page_token = None
        lsc = []
        while True:
            param = {}
            if page_token:
                param['pageToken'] = page_token
            children = self.drive.files().list(q="'"+self.folder+"' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false").execute()
            for child in children['files']:
                lsc.append(self.drive.files().get(fileId=child['id']).execute())
            page_token = children.get('nextPageToken')
            if not page_token:
                break
        return lsc
    
    def _write_reg(self):
        if self.reg_len > 0:
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': self.reg_len
                        }

                    }

                }
            ]
            result = self.docs.documents().batchUpdate(documentId=self.reg_id,body={'requests':requests}).execute()
        text = '\n'.join([k+'='+json.dumps(self.registry[k]) for k in self.registry.keys()])
        if text.endswith('}}'):
            text = text[:len(text)-1]
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1,
                    },
                    'text': text
                }
            }
        ]
        result = self.docs.documents().batchUpdate(documentId=self.reg_id,body={'requests':requests}).execute()
        self.reg_len = len(text)
    
    def store(self,key,obj,log=False):
        self._check()
        if key in self.registry.keys():
            raise ValueError('Key already exists in the registry.')
        if key.startswith('._'):
            raise ValueError('Key cannot start with ._')
        if '=' in key:
            raise ValueError('Key cannot contain "=".')

        if hasattr(obj,'read'):
            b64s = base64.b64encode(obj.read()).decode('utf-8')
            wasPython = False
        else:
            b64s = base64.b64encode(str(obj).encode('utf-8')).decode('utf-8')
            wasPython = True

        elen = len(b64s)
        if elen > 900000:
            parts = []
            jnr = ''
            for c in b64s:
                jnr += c
                if len(jnr) > 900000:
                    parts.append(jnr)
                    jnr = ''
            parts.append(jnr)
        else:
            parts = [b64s]
        
        c = 1
        ids = []
        for part in parts:
            if log:
                print('Storing part',c,'of',len(parts))
            name = 'stor_'+key+'_'+hashlib.sha256(str(random.random()*time.time()).encode('utf-8')).hexdigest()
            body = {
                'name':name,
                'mimeType':'application/vnd.google-apps.document',
                'parents':[self.folder]
            }
            f = self.drive.files().create(body=body).execute()
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1,
                        },
                        'text': part
                    }
                }
            ]
            result = self.docs.documents().batchUpdate(documentId=f['id'],body={'requests':requests}).execute()
            c += 1
            ids.append(f['id'])
            self.registry['._reserved_persistent']['all'].append(f['id'])

        self.registry[key] = {
            'length':elen,
            'files':ids,
            'wasPython':wasPython
        }
        self._write_reg()
    
    def read(self,key,ignore_errors=False):
        self._check()
        if key.startswith('._'):
            raise ValueError('Key cannot start with ._')
        if '=' in key:
            raise ValueError('Key cannot contain "=".')
        if key in self.registry.keys():
            fullstr = ''
            for i in self.registry[key]['files']:
                doc = self.docs.documents().get(documentId=i).execute()
                content = doc['body']['content'][1]['paragraph']['elements'][0]['textRun']['content'].strip()
                fullstr += content
            if len(fullstr) != self.registry[key]['length'] and not ignore_errors:
                raise ValueError('The data returned was malformed or corrupted.')
            
            if not self.registry[key]['wasPython']:
                return base64.b64decode(fullstr.encode('utf-8'))
            else:
                try:
                    return eval(base64.b64decode(fullstr.encode('utf-8')).decode('utf-8'))
                except:
                    return base64.b64decode(fullstr.encode('utf-8')).decode('utf-8')
        else:
            raise KeyError('Key '+str(key)+' not found.')
    
    def delete(self,key):
        self._check()
        if key.startswith('._'):
            raise ValueError('Key cannot start with ._')
        if '=' in key:
            raise ValueError('Key cannot contain "=".')
        if key in self.registry.keys():
            for k in self.registry[key]['files']:
                self.drive.files().delete(fileId=k).execute()
                try:
                    self.registry['._reserved_persistent']['all'].remove(k)
                except ValueError:
                    pass
            del self.registry[key]
            self._write_reg()
        else:
            raise KeyError('Key '+str(key)+' not found.')

if __name__ == '__main__':
    giss = GISS('ID')

    with open('__init__.py','rb') as f:
        giss.store('init.py',f,log=True)
    print(giss.registry)
    with open('giss_init.py','wb') as f:
        f.write(giss.read('init.py'))
    giss.delete('init.py')
    print(giss.registry)
    
    data = {
        'spam':'eggs',
        'eggs':'spam'
    }
    print(data,type(data))
    giss.store('spamneggs',data,log=True)
    print(giss.registry)
    ret = giss.read('spamneggs')
    print(ret,type(ret))
    giss.delete('spamneggs')
    print(giss.registry)
