#!/usr/bin/env python3
#
# A simple python based pastebin
#
# To run it: ../localpaste.py -f --debug
# To send input:   echo -n "hello" | curl -F 'clbin=<-' http://localhost:6542
# To get pastes:   curl http://localhost:6542/XXXX
#
# What it does not do:
#    - clean up old files (a simple cronjob can do this: find localpaste_data -type f -mtime +30 -delete)
#    - remove files on request (would need to log some authentication info for that... ip address, cookie, etc., or output a 2nd url with special privs)
#
# Copyright 2015 Peter Maloney
#
# License: Version 2 of the GNU GPL or any later version
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import socketserver
import argparse
import datetime
import time
import hashlib
import base64
import os
import http.server
import re
import socket
from urllib.parse import parse_qs

# more imports are below, based on usage of command line arguments, for modules:
#    ssl
#    pwd
#    grp

debug = 0

# http://stackoverflow.com/questions/24575121/in-python-how-to-print-full-iso-8601-timestamp-including-current-timezone
def get_timestamp_str():
    # get current local time and utc time
    localnow = datetime.datetime.now()
    utcnow = datetime.datetime.utcnow()

    # compute the time difference in seconds
    tzd = localnow - utcnow
    secs = tzd.days * 24 * 3600 + tzd.seconds

    # get a positive or negative prefix
    prefix = '+'
    if secs < 0:
        prefix = '-'
        secs = abs(secs)

    # print the local time with the difference, correctly formatted
    suffix = "%s%02d:%02d" % (prefix, secs/3600, secs/60%60)
    now = localnow.replace(microsecond=0)
    timestamp = "%s%s" % (now.isoformat(' '), suffix)
    return timestamp
    
def log(message):
    timestamp = get_timestamp_str()
    print("%s: %s" % (timestamp, message))
    
def logwarn(message):
    timestamp = get_timestamp_str()
    print("%s: WARNING: %s" % (timestamp, message))
    
def logerror(message):
    timestamp = get_timestamp_str()
    print("%s: ERROR: %s" % (timestamp, message))
    
def logdebug(args):
    if debug != 1:
        return
    
    if not isinstance(args, list) and not isinstance(args, tuple):
        # if it's not already iterable, make it iterable so the next code block handles all cases to avoid duplicating code
        args = [args]
        
    for item in args:
        for line in str(item).splitlines():
            log("DEBUG: %s" % line)

############################################
# CLI handling
############################################

parser = argparse.ArgumentParser(description='A daemon to record input in some temporary files.')
group = parser.add_mutually_exclusive_group()
group.add_argument('--foreground', '-f', action='store_const', const=True,
                   help='run in foreground mode')
group.add_argument('--daemon', '-d',  action='store_const', const=True,
                   help='run in daemon mode')
parser.add_argument('--debug', action='store_const', const=True,
                   help='run in debug mode')

parser.add_argument('--datadir', action='store',
                   type=str, default="localpaste_data",
                   help='dir to store data files (default=localpaste_data)')
parser.add_argument('--name-min-size', action='store',
                   type=int, default=4,
                   help='minimum number of chars in the name that goes in the url and filename (default=4)')
parser.add_argument('--name-max-size', action='store',
                   type=int, default=20,
                   help='maximum number of chars in the name that goes in the url and filename (default=20; do not use a number larger than 20)')
parser.add_argument('--data-max-size', action='store',
                   type=int, default=10*1024*1024,
                   help='maximum size in bytes for input data (default=10MiB)')
parser.add_argument('--no-create-datadir', action='store_const', const=True,
                   help='prevent automatically creating a data dir if one does not exist')
parser.add_argument('--user', action='store',
                   type=str,
                   help='run as root first and then the server will switch to this user after listening to the port')

parser.add_argument('--port', "-p", action='store',
                   type=int, default=None,
                   help='port to listen on')
parser.add_argument('--scheme', "-s", action='store',
                   type=str, default="http", choices=["http", "https"],
                   help='scheme to use (default=http)')
parser.add_argument('--hostname', action='store',
                   type=str, default=None,
                   help='hostname to send to clients in the url so they can retrieve their paste (default=use host and port from http request)')
parser.add_argument('--certfile', action='store',
                   type=str, default="server.pem",
                   help='file containing both the SSL certificate and key for https (default=server.pem)')
parser.add_argument('--listen-address', action='store',
                   type=str, default="0.0.0.0",
                   help='listen address (default=0.0.0.0)')

args = parser.parse_args()
debug = args.debug
logdebug("debug         = %s" % args.debug)
logdebug("foreground    = %s" % args.foreground)
logdebug("daemon        = %s" % args.daemon)
logdebug("datadir       = %s" % args.datadir)
logdebug("name-min-size = %s" % args.name_min_size)
logdebug("name-max-size = %s" % args.name_max_size)
logdebug("data-max-size = %s" % args.data_max_size)
logdebug("user          = %s" % args.user)
logdebug("port          = %s" % args.port)
logdebug("scheme        = %s" % args.scheme)
logdebug("hostname      = %s" % args.hostname)
logdebug("certfile      = %s" % args.certfile)
logdebug("listen-address= %s" % args.listen_address)
logdebug("argv          = %s" % sys.argv)

if not args.no_create_datadir and not os.path.isdir(args.datadir):
    os.mkdir(args.datadir)
elif args.no_create_datadir and not os.path.isdir(args.datadir):
    print("ERROR: datadir \"%s\" does not exist" % args.datadir)
    exit(1)

if args.port == None:
    args.port = 80
        
if args.scheme == "https":
    import ssl
    if not os.path.isfile(args.certfile):
        logerror("certfile \"%s\" was not found" % args.certfile)
        logerror("to generate a simple self-signed file, use:")
        logerror("    openssl req -new -x509 -keyout server.pem -out server.pem -days 365 -nodes")
        exit(1)
    if args.port == None:
        args.port = 443

hostname_and_port = None
if args.hostname:
    if not ( args.scheme == "http" and args.port == 80 ) or not ( args.scheme == "https" and args.port == 443 ):
        hostname_and_port = "%s:%s" % (args.hostname, args.port)
    else:
        hostname_and_port = "%s" % (args.hostname)

# For a text-only pastebin... but not sure if there's any advantage
#data_encoding = "utf-8"

# For supporting binary files... not sure if there's any disadvantage.
data_encoding = "latin1"

if not args.foreground and not args.daemon:
    logwarn("using default mode, which is currently foreground, but may change in the future")
    args.foreground = True
    
if args.name_max_size < 20:
    logerror("name_max_size cannot be larger than 20")
    exit(1)
        
############################################

# Based on:
# http://stackoverflow.com/questions/2699907/dropping-root-permissions-in-python
# But this version takes only a username, and figures out the group by taking the user's primary group
# This is most likely unix only
def drop_privileges(uid_name='localpaste'):
    import os, pwd, grp
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        logerror("You cannot drop privileges if you are not root")

        # this isn't really true... if you have CAP_SETUID and CAP_SETGID, you still can, and then you need to drop caps instead
        # TODO: support caps, and allow non-root to use this function
        
        exit(1)

    # Get the uid/gid from the name
    target_user = pwd.getpwnam(uid_name)
    
    target_uid = target_user.pw_uid
    target_gid = target_user.pw_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(target_gid)
    os.setuid(target_uid)

    # Ensure a very conservative umask
    old_umask = os.umask(0o077)

# just for dumping big strings in debug output, in case they are too large, shorten them    
def shorten_str(text, length=60):
    if len(text) > length:
        return "%s ... %s" % (text[0:int(length/2)], text[len(text)-int(length/2):])
    else:
        return text

class UnsupportedContentTypeException(Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)
        self.message = message

def read_data(file, length, content_type):
    # TODO: if possible, turn it into a stream into the file instead of a big string all in memory at once (a filter rather than slurping)
    
    read_total = 0
    ending = None
    oldline = None
    ignore_next = False
    logdebug("reading data...")
    
    if "multipart/form-data" in content_type:
        # first look for the marker and Content-Disposition
        # skip the useless \r\n
        while True:
            line = file.readline()
            read_total += len(line)
            logdebug("read a line: \"%s\"" % (shorten_str(line)))
        
            if not line:
                break
            
            try:
                line_str = line.decode(data_encoding).splitlines()[0]
            except:
                logwarn("failed to decode %s for str = %s... falling back to latin1" % (data_encoding, shorten_str(line)))
                line_str = line.decode("latin1").splitlines()[0]
            
            if "Content-Disposition:" in line_str:
                ending = oldline
                logdebug("found Content-Disposition; ending = \"%s\"" % ending)
                # next line is just "\r\n"... totally useless, so just remove it, since it's not real data
                line = file.readline()
                read_total += len(line)
                break
            else:
                oldline = line_str
                
        # then read data until the end, including the end marker and the useless \r\n at the end
        logdebug("read()")
        data = file.read(length - read_total)
        
        end_str = data[len(data)-len(ending)-4:].decode(data_encoding).splitlines()[0]

        if ending and ending in end_str:
            logdebug("end found")
            
        # remove the ending, plus the \r\n that is part of it, plus the \r\n on the next line, and the last \r\n inside the data
        data = data[0 : len(data)-len(ending)-6]
    elif content_type == "application/x-www-form-urlencoded":
        data = file.read(length)
        data_str = data.decode(data_encoding)
        data = parse_qs(data_str)["data"][0].encode(data_encoding)
    else:
        raise UnsupportedContentTypeException("Unsupported Content-Type: \"%s\"" % content_type)

    logdebug("done reading data...")

    return data

def read_file(filename):
    data = b""
    with open(os.path.join(args.datadir, filename), 'rb') as f:
        while True:
            chunk = f.read()
            if chunk:
                data += chunk
            else:
                break
    return data

# generate a short unique name
def generate_name():
    # start with high precision timestamp
    timestamp_str = str(time.time())
    #timestamp_str = "test value"
    ts_bytes = str.encode(timestamp_str)
    
    h = hashlib.sha1()
    h.update(ts_bytes)
    for l in range(args.name_min_size, args.name_max_size):
        # try larger and larger sizes to get smallest unique value
        for n in range(1, 100):
            # then hash it with sha1 (bytes, not hex str)
            # here we add n to the end, so first it was time1, then time12, then time123, ... time123...9899100 being hashed
            h.update(str.encode("%s" % n))
            hashbytes = h.digest()
            
            # then base64 it
            base64bytes = base64.b64encode(hashbytes)
            base64str = base64bytes.decode(data_encoding)
            
            # then remove slashes and dots
            base64str = base64str.replace("/", "")
            base64str = base64str.replace(".", "")
            
            # then shrink it to the target size
            check = base64str[0:l]
            if not os.path.isfile(os.path.join(args.datadir, check)):
                return check
        
    return None

def save_file(name, data):
    path=os.path.join(args.datadir, name)
    
    if os.path.isfile(path):
        logerror("the file \"%s\" already exists... failed to save paste" % path)
        
    # save the file
    with open(path, 'wb') as f:
        f.write(bytes(data))

class LocalPasteHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        logdebug("LocalPasteHandler.init() called")
        super(LocalPasteHandler, self).__init__(request, client_address, server)
        
    # For handling input
    def do_POST(self):
        client_supplied_hostname_and_port = None
        if "Host" in self.headers:
            client_supplied_hostname_and_port = self.headers["Host"]
        
        logdebug("LocalPasteHandler.handle() called")
        log("client %s - connected" % str(self.client_address))
        logdebug("client %s - calling read_report" % str(self.client_address))
        
        content_length = int(self.headers["Content-Length"])
        if content_length > args.data_max_size:
            self.send_response(400)
            self.end_headers()
            message = "Maximum content-length is %s, but recieved %s" % (args.data_max_size, content_length)
            self.wfile.write(message.encode(data_encoding))
            return
        
        content_type = self.headers["Content-Type"]
        try:
            data = read_data(self.rfile, content_length, content_type)
        except UnsupportedContentTypeException as e:
            # no printing to log here; already done in read_data
            self.send_response(500)
            self.end_headers()
            print(dir(e))
            message = e.message
            self.wfile.write(message.encode(data_encoding))
            
        logdebug("input was %s long" % len(data))

        if( len(data) == 0 ):
            self.send_response(400)
            self.end_headers()
            message = "empty data"
            self.wfile.write(message.encode(data_encoding))
            return
        
        # pick a name
        name = generate_name()
        logdebug("name = %s" % name)
        
        logdebug("client %s - calling save_file" % str(self.client_address))
        save_file(name, data)
        log("client %s - completed" % str(self.client_address))
        
        # Tell the client the name
        self.send_response(200)
        self.end_headers()
        
        # prepend a url
        if not hostname_and_port is None:
            use_hostname_and_port = hostname_and_port
        else:
            use_hostname_and_port = client_supplied_hostname_and_port
        message = "%s://%s/%s\r\n" % (args.scheme, use_hostname_and_port, name)
        self.wfile.write(message.encode(data_encoding))

    def write_paste_form(self):
        self.send_response(200)
        message = """<!doctype html>
            <html>
            <head>
                <title>LocalPaste CLI and web pastebin</title>
                <style type='text/css'>
                    .container {
                        margin: auto;
                        width: 70%;
                        height: 90%;
                        min-width: 500px;
                        max-width: 1000px;
                    }
                    .textarea {
                        width: 100%;
                        height: 100%;
                    }
                    .alignright {
                        float: right;
                    }
                </style>
            </head>
            <body>
                <form method='post' action="?">
                    <div class='container'>
                        <textarea class='textarea' name='data' rows='15' cols='50' ></textarea> <br />
                        <input class='alignright' type='submit' value='Paste' />
                    </div>
                </form>
            </body>
            </html>"""
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message.encode(data_encoding))
    
    def write_simple_error(code, message):
        self.send_response(400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message.encode(data_encoding))
        
    # For showing the pasted data
    def do_GET(self):
        path = self.path[1:]
        
        if len(path) == 0:
            # for blank path, show help and a paste form
            self.write_paste_form()
            return
        
        path_regex = re.compile("^[a-zA-Z0-9+=]+$")
        m = path_regex.match(path)
        if not m:
            logdebug("rejecting request: client = %s, path = %s" % (self.client_address, self.path))
            self.write_simple_error(400, "invalid file name")
            return
        
        data = read_file(path)
        logdebug("accepting request: client = %s, path = %s, len(data) = %s" % (self.client_address, self.path, len(data)))
        
        if( len(data) == 0 ):
            self.write_simple_error(400, "empty data")
            return
        
        self.send_response(200)
        self.end_headers()
        
        total = 0
        while total < len(data):
            # for some reason, it only writes 2539008 bytes at a time, so just keep trying that amount until done
            l = self.wfile.write(data[total:total+2539008])
            total += l
    
    def setup(self):
        logdebug("LocalPasteHandler.setup() called")
        super(LocalPasteHandler, self).setup()

class LocalPasteServer(http.server.HTTPServer, socketserver.ThreadingMixIn):
    def __init__(self, server_address, RequestHandlerClass):
        # no idea why this syntax doesn't work
        #super(LocalPasteServer, self).__init__(self, server_address, RequestHandlerClass)
        # this one works
        http.server.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        
        if args.scheme == "https":
            # This expects certfile= to contain both the private key and cert, generated like this:
            #    openssl req -new -x509 -keyout server.pem -out server.pem -days 365 -nodes
            # or you can probably just combine them yourself:
            #    cat server.key server.crt > server.pem
            # This was based on reading:
            #    https://gist.github.com/dergachev/7028596
            #    http://code.activestate.com/recipes/442473-simple-http-server-supporting-ssl-secure-communica/
            self.socket = ssl.wrap_socket(self.socket, certfile=args.certfile, server_side=True)

    # adding a timeout like in http://stackoverflow.com/questions/10003866/http-server-hangs-while-accepting-packets
    def finish_request(self, request, client_address):
        # timeout should only happen if content-length header is wrong
        request.settimeout(30)
        # "super" can not be used because BaseServer is not created from object
        http.server.HTTPServer.finish_request(self, request, client_address)
        
def run_server():
    socketserver.ThreadingMixIn.allow_reuse_address = True

    try:
        server = LocalPasteServer((args.listen_address, args.port), LocalPasteHandler)
        log("Starting server... hit ctrl+c to exit")
        if args.user:
            drop_privileges(args.user)
        server.serve_forever()
    except KeyboardInterrupt as e:
        log("Stopping server...")
        server.shutdown()
        raise
    
if args.foreground:
    run_server()
elif args.daemon:
    print("daemon mode not implemented... use nohup and foreground instead")
else:
    print("ERROR: Unknown mode; use one of the --daemon or --foreground options")
