# GISS
Google Infinite Storage Solution

### Setup

Download or clone the repository.

Run `pip install -r requirements.txt` in the project directory.

Create a new project in the Google API Console, and give it Drive and Docs api access. Download the `credentials.json` file into this folder.

Change `'ID'` on line 223 of `__init__.py` to the ID of an empty folder

Run `__init__.py` for a demo.

### Documentation

`GISS(folderId,path='credentials.json')`:
The main class of GISS. Every other method is a member of this class.

- `folderId`: the ID of your target folder
- `path`: the path to your `credentials.json` file

`GISS().store(key,obj)`:
Stores any python object or file object in GISS

- `key`: The name of the object. This should be unique.
- `obj`: A python object or file object to store. File objects stored this way must be open in `rb` mode.

**Returns:** None

`GISS().read(key)`:
Reads a stored object.

- `key`: Key of the object to read.

**Returns:** The object or file passed to `store()`. If it was a file, it can be passed to a `.write()` function.

`GISS().delete(key)`:
Deletes a stored object.

- `key`: Key of the object to delete.

**Returns:** None
