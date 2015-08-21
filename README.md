# localpaste
A simple python based pastebin you can run locally, with curl for input, just like clbin.com



Requirement: Python3

*Debian/Ubuntu OS:*
```
 apt-get install -y python3
```
*Fedora/CentOS/RedHat:*
compile from source

```
 yum install openssl-devel bzip2-devel expat-devel gdbm-devel readline-devel sqlite-devel
 
 wget https://www.python.org/ftp/python/3.4.3/Python-3.4.3.tar.xz
 
 tar xf Python-3.* 

 cd Python-3.*
 
 ./configure
 
 make
 
 sudo make install
 
```

Install
```
 git clone https://github.com/petermaloney/localpaste
 cd  localpaste/
```

```
  useradd localpaste
```

*Usage:*

 To run it:
 ```
 sudo nohup ./localpaste.py -f --user localpaste &
 ```
 
 To send input: 
 ```
 echo -n "hello" | curl -F 'clbin=<-' http://localhost/
 ```
 
 To get pastes:
```
 curl http://localhost/XXXX
```

Create an alias replace *localhost* with your Hostname/External IP

```
echo "alias lpaste=\"curl -F 'clbin=<-' http://localhost/"\" >> ~/.bashrc
```
 
 *Using your alias:*
 ````
cat <YOUR FILE>| lpaste
 
http://localhost/XXXX
```

*Creating and using a self-signed SSL Certificate*

```
openssl req -new -x509 -keyout server.pem -out server.pem -days 365 -nodes
```

The private key and cert must reside in the same folder as localpaste.py and be combined together in one file named **server.pem**. If your file has another name, you'll have to use the **--certfile** option to specify it's location. (e.g. --certfile /etc/myserver.pem)

```
sudo nohup ./localpaste.py --scheme https -f --user localpaste &
```

#  ./localpaste.py  -h

```
  usage: localpaste.py [-h] [--foreground | --daemon] [--debug]
                     [--datadir DATADIR] [--name-min-size NAME_MIN_SIZE]
                     [--no-create-datadir] [--user USER] [--port PORT]
                     [--scheme {http,https}] [--hostname HOSTNAME]
                     [--certfile CERTFILE] [--listen-address LISTEN_ADDRESS]

A daemon to record input in some temporary files.

optional arguments:
  -h, --help            show this help message and exit
  --foreground, -f      run in foreground mode
  --daemon, -d          run in daemon mode
  --debug               run in debug mode
  --datadir DATADIR     dir to store data files (default=localpaste_data)
  --name-min-size NAME_MIN_SIZE
                        minimum number of chars in the name that goes in the
                        url and filename (default=4)
  --no-create-datadir   prevent automatically creating a data dir if one does
                        not exist
  --user USER           run as root first and then the server will switch to
                        this user after listening to the port
  --port PORT, -p PORT  port to listen on
  --scheme {http,https}, -s {http,https}
                        scheme to use (default=http)
  --hostname HOSTNAME   hostname to send to clients in the url so they can
                        retrieve their paste (default=use host and port from
                        http request)
  --certfile CERTFILE   file containing both the SSL certificate and key for
                        https (default=server.pem)
  --listen-address LISTEN_ADDRESS
                        listen address (default=0.0.0.0)
```
