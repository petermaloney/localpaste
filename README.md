# localpaste
A simple python based pastebin you can run locally, with curl for input, just like clbin.com



Requirement: Python3

*Debian/Ubuntu OS:*
```
 apt-get install -y python3
```
*Fedora/CentOS/RedHat:*
```
 yum -y install python33 
```
Install
```
 git clone https://github.com/petermaloney/localpaste
 cd  localpaste/
```

*Usage:*
```
./localpaste.py -f --debug --hostname example.com
```
or
```
sudo ./localpaste.py -f --debug --hostname example.com
```

*Upload/Paste a file*

```
cat <YOUR FILE> | curl -F 'clbin=<-' http://example.com

```
Create an alias
 **replace example.com with your Hostname/IP**
```

echo -e "alias lpaste=\"curl -F 'clbin=<-' http://example.com\"" >> ~/.bashrc
```

```
cat <YOUR FILE>| lpaste

  http://example.com/TEST
```

```

  ./localpaste.py -h

usage: localpaste.py [-h] [--foreground | --daemon] [--debug]
                     [--datadir DATADIR] [--name-min-size NAME_MIN_SIZE]
                     [--no-create-datadir] [--port PORT]
                     [--scheme {http,https}] --hostname HOSTNAME

A daemon to record input in some temporary files.

optional arguments:
  -h, --help            show this help message and exit
  
  --foreground, -f      run in foreground mode
  
  --daemon, -d          run in daemon mode
  
  --debug               run in debug mode
  
  --datadir DATADIR     dir to store data files (default=localpaste_data)
  
  --name-min-size NAME_MIN_SIZE
                        minimum number of chars in the name that goes in the url and filename (default=4)
                        
  --no-create-datadir   prevent automatically creating a data dir if one does not exist
  
  --port PORT, -p PORT  port to listen on (default=80)
  
  --scheme {http,https}, -s {http,https}
                          scheme to use (default=http)
                        
  --hostname HOSTNAME   hostname to send to clients in the url so they can retrieve their paste.
```
