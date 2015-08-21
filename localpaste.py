#!/usr/bin/env python3
#
# A simple python based pastebin
#
# To run it: ../localpaste.py -f --debug
# To send input:   echo -n "hello" | curl -F 'clbin=<-' http://localhost:6542
# To get pastes:   curl http://localhost:6542/XXXX
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

############################################
# Config
############################################

# For sending URLs to clients, set these
scheme = "http"
server = "localhost"
port = 6542

# minimum number of chars in the name that goes in the url and filename
name_min_size = 4

work_dir = "localpaste_data"

############################################

debug = 0

if not ( scheme == "http" and port == 80 ) or not ( scheme == "https" and port == 443 ):
    server_and_port = "%s:%s" % (server, port)

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
    
def logdebug(args):
    if debug != 1:
        return
    
    if not isinstance(args, list) and not isinstance(args, tuple):
        # if it's not already iterable, make it iterable so the next code block handles all cases to avoid duplicating code
        args = [args]
        
    for item in args:
        for line in str(item).splitlines():
            log("DEBUG: %s" % line)

parser = argparse.ArgumentParser(description='A daemon to record input in some temporary files.')
group = parser.add_mutually_exclusive_group()
group.add_argument('--foreground', '-f', action='store_const', const=True,
                   help='run in foreground mode')
group.add_argument('--daemon', '-d',  action='store_const', const=True,
                   help='run in daemon mode')
group.add_argument('--stdin', '-c', action='store_const', const=True,
                   help='run in foreground stdin (test) mode')
parser.add_argument('--debug', action='store_const', const=True,
                   help='run in debug mode')

args = parser.parse_args()
debug = args.debug
logdebug("debug      = %s" % args.debug)
logdebug("foreground = %s" % args.foreground)
logdebug("daemon     = %s" % args.daemon)
logdebug("stdin      = %s" % args.stdin)
logdebug("argv       = %s" % sys.argv)

def read_data(file):
    data = b""

    ending = None
    oldline = None
    found_data = False
    ignore_next = False
    logdebug("reading data...")
    for line in file:
        line_str = line.decode("utf-8").splitlines()[0]
        logdebug("read a line: \"%s\"" % line)
        
        if ignore_next:
            ignore_next = False
        elif "Content-Disposition:" in line_str:
            found_data = True
            ending = oldline
            logdebug("found Content-Disposition; ending = %s" % ending)
            # next line is just "\r\n"... totally useless, so just remove it, since it's not real data
            ignore_next = True
        elif ending and ending in line_str:
            # don't read the rest... just finish
            break
        elif found_data:
            data += line
        else:
            oldline = line_str
            
    logdebug("done reading data...")
    if len(data) >= 2 and data[len(data)-2:] == b"\r\n":
        # there is a useless extra "\r\n" at the end... so just remove it, since it's not real data
        data = data[0:len(data)-2]
    return data

def read_file(filename):
    data = b""
    with open(os.path.join(work_dir, filename), 'rb') as f:
        line = f.read()
        data += line
    return data

# generate a short unique name
def generate_name():
    # start with high precision timestamp
    timestamp_str = str(time.time())
    ts_bytes = str.encode(timestamp_str)
    
    # then hash it with sha1 (bytes, not hex str)
    h = hashlib.sha1()
    h.update(ts_bytes)
    hashbytes = h.digest()
    
    # then base64 it
    base64bytes = base64.b64encode(hashbytes)
    base64str = base64bytes.decode("utf-8")
    
    # then remove slashes and dots
    base64str = base64str.replace("/", "")
    base64str = base64str.replace(".", "")
    
    # then shrink it to the smallest unique value, minimum 4 length
    ret = None
    for l in range(name_min_size, len(base64str)):
        check = base64str[0:l]
        if not os.path.isfile(check):
            ret = check
            break
    
    return ret

def save_file(name, data):
    # save the file
    with open(os.path.join(work_dir, name), 'wb') as f:
        f.write(bytes(data))

class LocalPasteHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        logdebug("LocalPasteHandler.init() called")
        super(LocalPasteHandler, self).__init__(request, client_address, server)
        
    # For handling input
    def do_POST(self):
        logdebug("LocalPasteHandler.handle() called")
        log("client %s - connected" % str(self.client_address))
        logdebug("client %s - calling read_report" % str(self.client_address))
        
        data = read_data(self.rfile)
        print("input was %s long" % len(data))
        
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
        message = "%s://%s/%s\r\n" % (scheme, server_and_port, name)
        self.wfile.write(message.encode("utf-8"))

    # For showing the pasted data
    def do_GET(self):
        path = self.path[1:]
        
        # TODO: for blank input, show help and a paste form
        
        path_regex = re.compile("^[a-zA-Z0-9+=]+$")
        m = path_regex.match(path)
        if not m:
            logdebug("rejecting request: client = %s, path = %s" % (self.client_address, self.path))
            self.send_response(400)
            self.end_headers()
            return
        
        data = read_file(path)
        logdebug("accepting request: client = %s, path = %s, len(data) = %s" % (self.client_address, self.path, len(data)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)
    
    def setup(self):
        logdebug("LocalPasteHandler.setup() called")
        super(LocalPasteHandler, self).setup()

class LocalPasteServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass

def run_server():
    host = "0.0.0.0"
    socketserver.ThreadingMixIn.allow_reuse_address = True

    try:
        server = LocalPasteServer((host, port), LocalPasteHandler)
        log("Starting server... hit ctrl+c to exit")
        server.serve_forever()
    except KeyboardInterrupt as e:
        log("Stopping server...")
        server.shutdown()
        raise
    
if args.stdin:
    report = read_report(sys.stdin)
    logdebug(report)
    db = dbconnect()
    try:
        insert_report(db, report)
    finally:
        db.close()
elif args.foreground:
    run_server()
elif args.daemon:
    print("daemon mode not implemented... use nohup and foreground instead")
else:
    print("ERROR: Unknown mode")
