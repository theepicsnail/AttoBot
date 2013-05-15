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
        """Read a character, and cache it, returning the character read (if any)"""
        read = self.stdout.read(1)
        self.line += read
        return read

    def popLine(self):
        """Pop off a line from the cached data."""
        line,self.line = self.line.split("\n",1)
        return line+"\n"
    
    def hasLine(self):
        """Returns whether the cached data has a full line"""
        return self.line.find("\n") != -1

    def fileno(self):
        """Override to allow select.select to poll the plugin"""
        return self.stdout.fileno()

    def write(self, line):
        """Send data to the underlying subprocess"""
        self.stdin.write(line)

    def __str__(self):
        return self.name

    def stop(self):
        """stops the underlying subprocess"""
        self.process.terminate()
    
    def isRunning(self):
        """returns if the subprocess has not exited yet"""
        return self.process.poll() == None    

class PluginManager:
    def __init__(self, cfgFile):
        self.mainPlugin = None
        self.loaded = {}
        self.config = ConfigParser()
        self.configFile = cfgFile
        self.rehash()

    def getProcesses(self):
        """Returns a list of all plugins, as well as the main plugin"""
        return self.loaded.values() + [self.mainPlugin]

    def launchPlugin(self, name):
        """Launches a new plugin, returning the plugin if it succeded"""
        p = Plugin(name, self.config.get(name,"exec"))
        print "Launched",name
        if p.isRunning():
            return p
        print "Failed."
        return None

    def rehash(self):
        """reread the config file"""
        self.config.read(self.configFile)
        
    def load(self, name):
        """Loads a plugin and stores it in the plugin table"""
        print "load:",name
        if self.loaded.has_key(name):
            print "Already loaded, reloading."
            self.unload(name)

        plugin = self.launchPlugin(name)

        if plugin:
            self.loaded[name] = plugin
        else:
            print "Failed to load"

    def unload(self, name):
        """Stops a plugin and removes it from the plugin table"""
        print "unload:",name
        if not self.loaded.has_key(name):
            print "Not loaded. Skipping."
            return
        self.loaded[name].stop()
        del self.loaded[name]
        print "Unloaded"
    
    def startMain(self):
        """Starts the main exec and returns whether it was a successful start"""
        self.mainPlugin = self.launchPlugin("main")
        return self.mainPlugin is not None

    def startPlugins(self):
        """Starts the (non main) plugins and stores them all in the plugin table"""
        for plugin in self.config.sections():
            if plugin != "main":
                self.load(plugin)

if __name__ =="__main__":

    def handleCommand(line):
        """When this script is run unbuffered, this will process typed in commands and allow
        management from the cli
        
        plugins -> list all the plugins and their loaded/unloaded state.

        rehash -> reload the config file

        load [plugin] -> load the specified plugin

        unload [plugin] -> unload the specified plugin
        """
        parts = line.split(" ")
        if parts[0] == "plugins":
            for section in manager.config.sections():
                prefix = "+" if manager.loaded.has_key(section) or section == "main" else "-"
                print prefix, section
        elif parts[0] == "rehash":
            manager.rehash()
        elif parts[0] == "load":
            manager.load(parts[1])
        elif parts[0] == "unload":
            manager.unload(parts[1])


    #start up our main process and load the plugins
    manager = PluginManager("irc.cfg")
    if not manager.startMain():
        print "Failed to start main exec."
        exit(1)
    manager.startPlugins()

    #Main loop
    stdinBuffer = ""
    while True:
        #read everything from stdin and then pass it to handleCommand
        r, _, _ = select([stdin],[],[],0)
        while r:
            c = stdin.read(1)
            r, _, _ = select([stdin],[],[],0)
            if not r:
                handleCommand(stdinBuffer)
                stdinBuffer = ""
            else:
                stdinBuffer += c
        
        #read everything from all of the processe
        plugins = manager.getProcesses()
        r, _, _ = select(plugins,[],[], 1)
        deadPlugins = []
        while r:
            for plugin in r:
                if not plugin.read(): #Plugin has no more data apparently.
                    print plugin,"had an empty read."
                    print plugin,"Buffer: '%s'"%plugin.line
                    
                    #pull it out of the plugins list so we stop polling it
                    idx = plugins.index(plugin)
                    p = plugins.pop(idx)
                    if not p.hasLine():
                        #only mark the plugin as dead once its buffer has drained.
                        deadPlugins.append(p.name)
            r, _, _ = select(plugins,[],[], 0)

        #pass messages around
        for plugin in manager.getProcesses():
            while plugin.hasLine():
                line = plugin.popLine()
                print "Got line: [%s] %s" %(plugin, line)

                #server sent a message, forward to plugins
                if plugin.name == "main": 
                    for p in manager.loaded.values():
                        try:
                            p.write(line)
                        except:pass

                else: # a plugin said something, send to server
                    try:
                        print "Sending '%s' to main plugin" % line
                        manager.mainPlugin.write(line)
                    except:
                        print "Main process died."
                        try:
                            while manager.mainPlugin.read():
                                pass
                        except:pass
                        print "Main processes last buffer:"
                        print manager.mainPlugin.line
                        exit(0)

        #clean up any dead plugins.
        for p in deadPlugins:
            manager.unload(p)
