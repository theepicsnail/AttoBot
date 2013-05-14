from subprocess import *
from select import *
from sys import *
from shlex import *
from ConfigParser import *

class Plugin:
    def __init__(self, name, cmd):
        self.name = name
        cmd = list(split(cmd))
        self.cmd = cmd
        self.process = Popen(cmd, stdin=PIPE, stdout=PIPE)
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.line = ""

    def read(self):
        read = self.stdout.read(1)
        self.line += read
        return read
    def popLine(self):
        line = self.line
        self.line = ""
        return line
    def fileno(self):
        return self.stdout.fileno()
    def write(self, line):
        self.stdin.write(line)
    def __str__(self):
        return self.name
    def stop(self):
        self.process.terminate()
if __name__ =="__main__":
    def loadPlugin(name):
        print "Loading", name
        plugins[name] = Plugin(name, config.get(name,"exec"))
    def unloadPlugin(name):
        print "Unloading", name
        plugins[name].stop()
        del plugins[name]

    def handleCommand(line):
        parts = line.split(" ")
        if parts[0] == "plugins":
            for section in config.sections():
                prefix = "+" if plugins.has_key(section) or section == "main" else "-"
                print prefix, section
        elif parts[0] == "rehash":
            config.read("irc.cfg")
        elif "load" in parts[0]: #load and unload
            if plugins.has_key(parts[1]):
                unloadPlugin(parts[1])
            if parts[0] == "load":
                loadPlugin(parts[1])

    config = ConfigParser()
    config.read("irc.cfg")
    mainExec = config.get("main","exec") 
    net = Plugin("main", mainExec)
    plugins = {}
    for section in config.sections():
        if section == "main":
            continue
        loadPlugin(section)
    stdinBuffer = ""
    while True:
        r, _, _ = select([stdin],[],[],0)
        while r:
            c = stdin.read(1)
            r, _, _ = select([stdin],[],[],0)
            if not r:
                handleCommand(stdinBuffer)
                stdinBuffer = ""
            else:
                stdinBuffer += c
        r, _, _ = select([net] + plugins.values(),[],[], 1)
        for plugin in r:
            v = plugin.read()
            if v:
                if v == "\n":
                    line = plugin.popLine()
                    if plugin == net:
                        deadPlugins = []
                        for p in plugins.values():
                            try:
                                p.write(line)
                            except:
                                deadPlugins.append(p.name)
                        for p in deadPlugins:
                            unloadPlugin(p)
                    else:
                        net.write(line)
            else:
                break        
    print "End of loop."
            #if data.startswith("PING"):
            #    p.stdout.write(data.replace("PING","PONG"))
