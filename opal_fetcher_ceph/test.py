import urllib.request
import tarfile
import json
import requests
from io import BytesIO
url = "http://hk-qaopabs-2011/bundles/data/contactsapi.51.tar.gz"
# ftpstream = urllib.request.urlopen(url)
# thetarfile = tarfile.open(fileobj=ftpstream, mode="r|gz")
# print(thetarfile)
# f = thetarfile.extractall()
# data = f.read
# print(data)
# data = thetarfile.extractfile("data.json")
# jsonData = json.loads(data.read())
# print(jsonData)

# response = requests.get(url, stream=True)

# file = tarfile.open("/Users/arifat/Downloads/contactsapi.51.tar.gz")
# data = file.extractfile("/data.json")
# print(data)
# jsonData = json.loads(data.read())
# print(jsonData)

# response = requests.get(url, stream=True)
# thetarfile = tarfile.open(fileobj=response.raw, mode="r|gz")
# data = thetarfile.extractfile("/data.json")
# print(data.read())
# jsonData = json.loads(data.read())
# print(jsonData)

ftpstream = urllib.request.urlopen(url)
# BytesIO creates an in-memory temporary file.
# See the Python manual: http://docs.python.org/3/library/io.html
tmpfile = BytesIO()
while True:
    # Download a piece of the file from the connection
    s = ftpstream.read(16384)

    # Once the entire file has been downloaded, tarfile returns b''
    # (the empty bytes) which is a falsey value
    if not s:  
        break

    # Otherwise, write the piece of the file to the temporary file.
    tmpfile.write(s)
ftpstream.close()

# Now that the FTP stream has been downloaded to the temporary file,
# we can ditch the FTP stream and have the tarfile module work with
# the temporary file.  Begin by seeking back to the beginning of the
# temporary file.
tmpfile.seek(0)

# Now tell the tarfile module that you're using a file object
# that supports seeking backward.
# r|gz forbids seeking backward; r:gz allows seeking backward
tfile = tarfile.open(fileobj=tmpfile, mode="r:gz")

# You want to limit it to the .nxml files
tfile_data = [filename
                  for filename in tfile.getnames()
                  if filename.endswith('.json')]

tfile_extract1 = tfile.extractfile(tfile_data[0])
tfile_extract1_text = tfile_extract1.read()
jsonData = json.loads(tfile_extract1_text)
print(jsonData)
# And when you're done extracting members:
tfile.close()
tmpfile.close()