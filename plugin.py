#           Sonos Plugin
#
#           Original author:    Tester22, 2017, https://github.com/tester22/Domoticz-Sonos
#           Current author:     G3rard, 2017
#
"""
<plugin key="Sonos" name="Sonos Players" author="G3rard" version="0.91" wikilink="https://github.com/gerard33/sonos" externallink="https://sonos.com/">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="192.168.1.161"/>
        <param field="Mode1" label="Update interval (sec)" width="100px" required="true" default="30"/>
        <param field="Mode2" label="Icon" width="100px">
            <options>
                <option label="Sonos" value="Sonos" default="true" />
                <option label="Sonos 1" value="Sonos1"/>
                <option label="Sonos 5" value="Sonos5"/>
            </options>
        </param>
        <param field="Mode3" label="Notifications" width="100px">
            <options>
                <option label="True" value="True"/>
                <option label="False" value="False" default="true" />
            </options>
        </param>
        <param field="Mode4" label="Notification folder" width="400px" required="true" default="http://<domoticz_ip>:8080/notifications"/>
        <param field="Mode5" label="Refresh radio list" width="100px">
            <options>
                <option label="True" value="Refresh"/>
                <option label="False" value="No_refresh" default="true" />
            </options>
        </param>
        <param field="Mode6" label="Debug" width="100px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
                <option label="Logging" value="File"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import http.client
import time
import html
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

class BasePlugin:
    # player status
    playerState = 0             #0=off, 1=playing, 2=paused
    mediaLevel = 0              #volume
    mediaDescription = ""       #what is playing
    muted = 2                   #0=muted, 2=not muted
    creator = None              #artist or radio station
    title = None                #name of song
    radioState = 0              #1=radio playing
    sourceOptions = {}          #dict with options for control
    sourceOptions2 = {}         #dict with options for control
    sonosControl = 0            #selector switch value control
    sonosRadio = 0              #selector switch value radio
    CurrentURI = None           #url for radio from GetMediaInfo
    TrackURI = None             #url for song from GetPositionInfo
    RelTime = None              #time played of song from GetPositionInfo
    Track = None                #track number of song
    radioFavorites = {}         #dict for radio stations in favorites
    
    # Executed once at reboot/update, can create up to 255 devices
    def onStart(self):
        if Parameters["Mode6"] != "Normal":
            Domoticz.Debugging(1)
            DumpConfigToLog()

        self.SourceOptions =    { "LevelActions"  : "||||", 
                                  "LevelNames"    : "Off|Previous|Play|Pause|Next",
                                  "LevelOffHidden": "true",
                                  "SelectorStyle" : "0"
                                }

        # Check if images are in database
        if 'Sonos'  not in Images: Domoticz.Image('Sonos.zip').Create()
        if 'Sonos1' not in Images: Domoticz.Image('Sonos1.zip').Create()
        if 'Sonos5' not in Images: Domoticz.Image('Sonos5.zip').Create()
        
        # Create devices if required
        if 1 not in Devices:
            Domoticz.Device(Name="Status",  Unit=1, Type=17,  Switchtype=17, Used=1).Create()
            Domoticz.Log("Status device created")
        if 2 not in Devices:
            Domoticz.Device(Name="Volume",  Unit=2, Type=244, Subtype=73, Switchtype=7,  Image=8, Used=1).Create()
            Domoticz.Log("Volume device created.")
        if 3 not in Devices:
            Domoticz.Device(Name="Control", Unit=3, TypeName="Selector Switch", Switchtype=18, Image=8, Options=self.SourceOptions, Used=1).Create()
            Domoticz.Log("Control device created")
        
        # Create or update radio stations selector switch
        self.sonos_GetFavorites()
        LogMessage("Number of radio stations in favorites: " + str(len(self.radioFavorites)))
        sradioStations = sorted(list(self.radioFavorites.keys()))   #get radiostations in sorted list, source is key in dict
        sradioStations = '|'.join(sradioStations)                   #get radiostations in string, divided with | for selector switch
        LogMessage("Radio stations in favorites: " + str(sradioStations))
        self.SourceOptions2 =   { "LevelActions"  : "|"*int(len(self.radioFavorites)), 
                                  "LevelNames"    : "Off|" + sradioStations,
                                  "LevelOffHidden": "false",
                                  "SelectorStyle" : "1"
                                }
        if 4 not in Devices:
            Domoticz.Device(Name="Radio", Unit=4, TypeName="Selector Switch", Switchtype=18, Image=8, Options=self.SourceOptions2, Used=1).Create()
            Domoticz.Log("Radio device created")
        if 4 in Devices and Parameters["Mode5"] == "Refresh":
            Devices[4].Delete()
            Domoticz.Device(Name="Radio", Unit=4, TypeName="Selector Switch", Switchtype=18, Image=8, Options=self.SourceOptions2, Used=1).Create()
            Domoticz.Log("Radio device updated (device will be on last position of Switches tab...)")
            Domoticz.Log("Number of radio stations in favorites: " + str(len(self.radioFavorites)))
            Domoticz.Log("Radio stations in favorites: " + str(sradioStations))
        
        # Update images and status
        if 1 in Devices:
            UpdateImage(1)
            self.playerState = Devices[1].nValue
        if 2 in Devices:
            self.mediaLevel = Devices[2].nValue
        if 3 in Devices:
            UpdateImage(3)
            self.sonosControl = Devices[3].sValue
        if 4 in Devices:
            UpdateImage(4)
            self.sonosControl = Devices[3].sValue

        # Add notifier if required
        if Parameters["Mode3"] == "True":
            notifierName = Devices[1].Name                  #use hardware name from device name
            notifierName = notifierName.split(' -')[0]      #remove everything after -
            notifierName = notifierName.replace(' ', '_')   #replace spaces by underscore
            notifierName = notifierName.lower()             #lower case
            Domoticz.Notifier(notifierName)                 #add notifier
            Domoticz.Log("Notifier '" + notifierName + "' added")

        # Set refresh
        if is_number(Parameters["Mode1"]):
            if int(Parameters["Mode1"]) < 30:
                Domoticz.Log("Update interval set to " + Parameters["Mode1"])
                Domoticz.Heartbeat(int(Parameters["Mode1"]))
            else:
                Domoticz.Heartbeat(30)
        else:
            Domoticz.Heartbeat(30)
        return

    # Executed each time we click on device through Domoticz GUI
    def onCommand(self, Unit, Command, Level, Hue):
        LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "'")
    
        Command = Command.strip()
        action, sep, params = Command.partition(' ')
        action = action.capitalize()

        if Unit == 1:  # Playback control
            if action == 'On':
                self.sonos_SetCommand('Play')
                self.playerState = 1
            elif action == 'Off':
                self.sonos_SetCommand('Stop')
                self.playerState = 0
                self.mediaDescription = 'Off'
        if self.playerState == 1 or self.playerState == 2: # Only react to switches when Sonos is on or paused
            if Unit == 2:  # Volume control
                if action == 'Set' and (params.capitalize() == 'Level' or Command.lower() == 'Volume'):
                    self.mediaLevel = Level
                    self.sonos_SetVolume(str(self.mediaLevel))
                    # Send an update request to get updated data from the player
                    self.sonos_GetVolume
                elif action == 'On' or action == 'Off':
                    if action == 'On':
                        DesiredMute = "0"
                        self.muted = 8 #2
                    else:
                        DesiredMute = "1"
                        self.muted = 0
                    self.sonos_SetMute(DesiredMute)
            if Unit == 3: # Control
                if Level == 10:                         #Previous
                    self.sonos_SetCommand('Previous')
                if Level == 20:                         #Play
                    self.sonos_SetCommand('Play')
                    self.playerState = 1
                if Level == 30:                         #Pause
                    self.sonos_SetCommand('Pause')
                    self.playerState = 2
                    self.mediaDescription = 'Paused'
                if Level == 40:                         #Next
                    self.sonos_SetCommand('Next')
                self.sonosControl = Level
            if Unit == 4: # Radio
                if Level == 0:
                    LogMessage("Radio station selector set to off")
                else:
                    dictOptions = Devices[4].Options
                    listLevelNames = dictOptions['LevelNames'].split('|')
                    strSelectedName = listLevelNames[int(int(Level)/10)]
                    uriRadio = self.radioFavorites[strSelectedName]         #get uri radio belonging to this key
                    Domoticz.Log(strSelectedName + ", " + uriRadio)
                    self.sonos_SetRadio(uriRadio, strSelectedName)
                    self.sonos_SetCommand('Play')
                self.sonosRadio = Level
        self.SyncDevices()
        return

    # Executed when notification is send from Domoticz to the hardware
    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        LogMessage("Notification: " + Name + ", " + Status + ", " + Subject + ", " + Text + ", " + str(Priority) + ", " + Sound)
        if Parameters["Mode3"] == "True":
            # Example notification: doorbell.mp3/30
            if "/" in Subject:
                notificationFile = Subject.split('/')[0]
                notificationVolume = Subject.split('/')[1]
            else:
                notificationFile = Subject
                notificationVolume = "10" #default volume            
            # Get what's playing and volume
            saveVolume = self.sonos_GetVolume()
            savePositionInfo, saveTrackURI, saveTime, saveTrack = self.sonos_GetPositionInfo()
            saveMediainfo, saveURI, saveStation = self.sonos_GetMediaInfo()
            #saveTrackURI = saveTrackURI.split("?")[0]
            LogMessage(">> Show what is currently playing before switching to notification")
            LogMessage("Current volume: " + str(saveVolume))
            if self.radioState == 1:
                LogMessage("Current URI: " + str(saveURI) + ". Current radio station: " + str(saveStation))
            else:
                LogMessage("Currently playing: " + str(savePositionInfo) + ". Current URI: " + str(saveURI))
                LogMessage("Current time in song: " + str(saveTime) + ". Number: " +str(saveTrack))
            
            # Pause when Sonos is on
            if self.playerState == 1:
                wasOn = True
                self.sonos_SetCommand('Pause')
            else:
                wasOn = False
            # Check if Sonos is muted, if yes then unmute
            if self.muted == 0:
                wasMuted = True
                DesiredMute = "0"
                self.sonos_SetMute(DesiredMute)
            else:
                wasMuted = False
            
            # Get information on path and file
            slash = "" if str(Parameters["Mode4"]).endswith("/") else "/"
            # Check if path is a http website
            if str(Parameters["Mode4"]).startswith("http"):
                try:
                    ret = urllib.request.urlopen(str(Parameters["Mode4"]) + slash + notificationFile)
                    LogMessage("Notification: file '" + notificationFile + "' found")
                    self.sonos_SetAVTransportURI(str(Parameters["Mode4"] + slash + notificationFile))
                    notificationReady2Play = True
                except (urllib.error.HTTPError, urllib.error.URLError) as e:
                    Domoticz.Error("Notification: file '" + notificationFile + "' not found. " + str(e))
                    notificationReady2Play = False
            # Path is a network share
            elif str(Parameters["Mode4"]).startswith("//"):
                ###trying to find a way to check if file on smb share exist
                ###from smb.SMBConnection import SMBConnection is not working
                '''
                try:
                    with open("smb:" + str(Parameters["Mode4"]) + slash + notificationFile) as file:
                        LogMessage("Notification: file '" + notificationFile + "' found")
                        self.sonos_SetAVTransportURI("x-file-cifs:" + str(Parameters["Mode4"] + slash + notificationFile))
                        notificationReady2Play = True
                        pass
                except IOError as e:
                    Domoticz.Error("Notification: file '" + notificationFile + "' not found. " + str(e))
                    notificationReady2Play = False
                
                or

                try:
                    ret = urllib.request.urlopen("smb:" + str(Parameters["Mode4"]) + slash + notificationFile)
                    LogMessage("Notification: file '" + notificationFile + "' found")
                    self.sonos_SetAVTransportURI("x-file-cifs:" + str(Parameters["Mode4"] + slash + notificationFile))
                    notificationReady2Play = True
                except (urllib.error.HTTPError, urllib.error.URLError) as e:
                    Domoticz.Error("Notification: file '" + notificationFile + "' not found. " + str(e))
                    notificationReady2Play = False
                '''
                self.sonos_SetAVTransportURI("x-file-cifs:" + str(Parameters["Mode4"] + slash + notificationFile))
                notificationReady2Play = True
            else:
                Domoticz.Error("Notification folder '" + str(Parameters["Mode4"]) + "'not starting with 'http' or '//'")
                notificationReady2Play = False
            
            # Set volume and play notification
            if notificationReady2Play:
                self.sonos_SetVolume(str(notificationVolume))
                self.sonos_SetCommand('Play')
                Domoticz.Log("Notification '" + str(notificationFile) + "' played with volume " + str(notificationVolume))
                # Small pause needed when Sonos was off before playing notification, otherwise script won't see that Sonos is playing notification
                if wasOn == False:
                    if self.sonos_GetTransportInfo() == 0:
                        time.sleep(1)   #delays for 1 second
                # Check if file is still playing
                while self.sonos_GetTransportInfo() == 1:
                    time.sleep(1)   #delays for 1 second
                    LogMessage("Notification is playing")

            # Restore what was playing and volume
            if wasMuted:
                wasMuted = False
                DesiredMute = "1"
                self.sonos_SetMute(DesiredMute)
            self.sonos_SetVolume(str(saveVolume))

            if self.radioState == 1:
                self.sonos_SetRadio(str(saveURI), str(saveStation)) #use CurrentURI from GetMediaInfo, using TrackURI is also possible
            else:
                self.sonos_SetAVTransportURI(str(saveURI)) #use CurrentURI from GetMediaInfo to restore the queue, using TrackURI ignores the queue
                self.sonos_Seek("TRACK_NR", str(saveTrack))
                self.sonos_Seek("REL_TIME", str(saveTime))
            
            # Play if previous list was playing
            if wasOn:
                self.sonos_SetCommand('Play')
                wasOn = False
        return

    # Execution depend of Domoticz.Heartbeat(x) x in seconds
    def onHeartbeat(self):
        # Check if Sonos is on and available
        try:
            self.sonos_GetTransportInfo()
        except Exception as err:
            Domoticz.Error("Sonos not available (" +  str(err) + ")")
            return
        # Don't update mediainfo if player is stopped
        if self.playerState == 1:
            self.sonos_GetPositionInfo()
        self.sonos_GetVolume()
        self.sonos_GetMute()
        if self.playerState == 1:
            if self.radioState == 1:
                LogMessage("Sonos is playing radio")
                self.sonos_GetMediaInfo()
                ###Dit zorgt ervoor dat de switch aangaat als de radio aan is, maar zorgt ook voor dat switch altijd op svalue 0 wordt voor update met SyncRadioStation
                #UpdateDevice(4, 1, str(self.sonosRadio))
                self.SyncRadioStation()
            else:
                self.sonosRadio = 0
                UpdateDevice(4, 1, str(self.sonosRadio))
        elif self.playerState == 0:
            self.sonosRadio = 0             #set radio selector to off when no radio is played
            ###Naar SyncDevices, maar daar juist uitgezet?
            UpdateDevice(4, 0, str(self.sonosRadio))
        self.SyncDevices()
        return

    # Sends message to Sonos
    def sendMessage(self, data, method, url):
        conn = http.client.HTTPConnection(Parameters["Address"] + ":1400")
        headers = {"Content-Type": 'text/xml; charset="utf-8"', "SOAPACTION": method}
        conn.request("POST", url, data, headers)
        response = conn.getresponse()
        conn.close()
    
        if response.status == 200:
            data = response.read().decode("utf-8")
            LogMessage(str(data))
            self.parseMessage(data)
        else:
            Domoticz.Error("Unexpected response status received in function sendMessage (" + str(response.status) + ", " + str(response.reason) + "). \
                            The following command is sent: " + str(method) + ", " + str(url))
        return
    
    # Process message from Sonos
    def parseMessage(self, Data):
        LogMessage(unescape(Data)) #DumpHTTPResponseToLog(Data)
        strData = str(Data)
        # Is Sonos muted
        if strData.find('CurrentMute') > 0:
            sonosMuteResponse = extractTagValue('CurrentMute', strData)
            LogMessage("Sonos mute status: " + str(sonosMuteResponse))
            if sonosMuteResponse == "1": # Muted
                self.muted = 8 #0, shows Sound 0, nvalues can be found on https://github.com/domoticz/domoticz/blob/494fff71685f319b25e7824684c299162b19f8c3/main/RFXNames.cpp#L1396
            else:
                self.muted = 2
        # Check volume of Sonos
        if strData.find('CurrentVolume') > 0:
            self.mediaLevel = extractTagValue('CurrentVolume', strData)
            LogMessage("Sonos volume: " + str(self.mediaLevel))
        # Check if Sonos is on
        if strData.find('CurrentTransportState') > 0:
            CurrentTransportState = extractTagValue('CurrentTransportState', strData).upper()
            LogMessage("Sonos state: " + str(CurrentTransportState))
            if CurrentTransportState != None:
                if CurrentTransportState  == 'PLAYING':
                    self.playerState = 1
                    UpdateDevice(3, 1, str(self.sonosControl))
                if CurrentTransportState  == 'PAUSED_PLAYBACK':
                    self.playerState = 2
                    self.mediaDescription = 'Paused'
                    UpdateDevice(1, self.playerState, self.mediaDescription)
                if CurrentTransportState  == 'STOPPED':
                    self.playerState = 0
                    self.mediaDescription = 'Off'
                    UpdateDevice(1, self.playerState, self.mediaDescription)
                    self.sonosControl = 0
                    UpdateDevice(3, 0, str(self.sonosControl))
        # Check what is playing on Sonos
        if strData.find('TrackMetaData') > 0:
            if extractTagValue('TrackMetaData', strData).upper() == "NOT_IMPLEMENTED":
                self.mediaDescription = "Grouped"
                self.playerState = 0
                UpdateDevice(1, self.playerState, self.mediaDescription)
            else:
                strData = unescape(strData)
                if 'dc:creator' in strData and self.playerState == 1:
                    self.radioState = 0
                    self.creator = extractTagValue('dc:creator', strData)
                    self.title = extractTagValue('dc:title', strData)
                    dash = "" if not self.title else " - "
                    self.mediaDescription = str(self.creator) + dash + str(self.title)
                    UpdateDevice(1, self.playerState, self.mediaDescription)
                else: #radiostation
                    self.radioState = 1
                    LogMessage('Sonos playing radio')
                    self.title = extractTagValue('r:streamContent', strData)
                    if self.title == "ZPSTR_CONNECTING": self.title = ''
                
                # Get TrackURI and RelTime (time played) for notification
                self.TrackURI = extractTagValue('TrackURI', strData)
                self.RelTime = extractTagValue('RelTime', strData)
                self.Track = extractTagValue('Track', strData)
        # If radio is playing check the radio station
        if strData.find('CurrentURIMetaData') > 0:
            strData = unescape(strData)
            #Domoticz.Log(strData)
            if "dc:title" in strData: self.creator = extractTagValue('dc:title', strData)
            dash = "" if not self.title else " - "
            self.mediaDescription = str(self.creator) + dash + str(self.title)
            ### is voor notification, maar nog nodig? omdat url uit GetPositionInfo gehaald wordt
            self.CurrentURI = extractTagValue('CurrentURI', strData)
            if self.radioState == 1 and self.playerState == 1:
                UpdateDevice(1, self.playerState, self.mediaDescription)
        # Radio stations in favorites of TuneIn - My Radiostations
        if strData.find('ContentDirectory') > 0:
            strData = unescape(strData)
            LogMessage("---Radio stations XML---")
            LogMessage(strData) #DumpHTTPResponseToLog(Data)
            metadata = ET.fromstring(strData)
            for item in metadata.findall('.//*{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item'):
                title = uri = None
                uri = item.findtext('{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}res')
                title = item.findtext('{http://purl.org/dc/elements/1.1/}title')
                if title and uri: self.radioFavorites[title] = uri
            LogMessage("Radio stations dict: " + str(self.radioFavorites))
            LogMessage("Total radio stations favorites: " + str(len(self.radioFavorites)))
        return

    # Check if radio station being played is in favorites and selector switch is not on that station
    def SyncRadioStation(self):
        radioURI = html.escape(self.CurrentURI)             #escape the uri for &
        LogMessage("Current radio URI: " + radioURI)
        radioStationFound = False
        for k,v in self.radioFavorites.items():
            if radioURI == html.escape(v):                  #if CurrentURI is found in the values of the radio favorites dict
                LogMessage('Radio station found in favorites list, updating radio switch selector')
                dictOptions = Devices[4].Options
                listLevelNames = dictOptions['LevelNames'].split('|')
                radioLevel = (listLevelNames.index(k))*10   #get the index and multiply it with 10 to get the level of selector switch
                self.sonosRadio = radioLevel
                UpdateDevice(4, 1, str(self.sonosRadio))
                radioStationFound = True
                ###self.SyncDevices()
        if radioStationFound == False:
            LogMessage('Radio station not found in favorites list, updating radio switch selector')
            self.sonosRadio = 0
            UpdateDevice(4, 1, str(self.sonosRadio))
        return

    # Make sure that the Domoticz devices are in sync
    def SyncDevices(self):
        UpdateDevice(1, self.playerState, self.mediaDescription)
        if self.playerState == 0:
            UpdateDevice(2, 0, str(self.mediaLevel))
            self.sonosControl = 0
            UpdateDevice(3, 0, str(self.sonosControl))
            self.radioState = 0
            UpdateDevice(4, 0, str(self.sonosRadio))
        else:
            UpdateDevice(2, self.muted, str(self.mediaLevel))
            UpdateDevice(3, 1, str(self.sonosControl))
            #UpdateDevice(4, 1, str(self.sonosRadio))
        return

    ###### SONOS COMMANDS ######
    def sonos_GetTransportInfo(self):
        '''Checks if Sonos is on, 0=off, 1=playing, 2=paused'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                    </u:GetTransportInfo>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo', "/MediaRenderer/AVTransport/Control")
        return self.playerState

    def sonos_GetPositionInfo(self):
        '''Gives author-song which is being played'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Channel>Master</Channel>\
                                    </u:GetPositionInfo>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo', "/MediaRenderer/AVTransport/Control")
        return self.mediaDescription, self.TrackURI, self.RelTime, self.Track

    def sonos_GetMediaInfo(self):
        '''Gives radio station-song which is being played'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:GetMediaInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                    </u:GetMediaInfo>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#GetMediaInfo', "/MediaRenderer/AVTransport/Control")
        return self.mediaDescription, self.CurrentURI, self.creator

    def sonos_GetVolume(self):
        '''Gives volume'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Channel>Master</Channel>\
                                    </u:GetVolume>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:RenderingControl:1#GetVolume', "/MediaRenderer/RenderingControl/Control")
        return self.mediaLevel

    def sonos_GetMute(self):
        '''Gives mute state, #0=muted, 2=not muted'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Channel>Master</Channel>\
                                    </u:GetMute>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:RenderingControl:1#GetMute', "/MediaRenderer/RenderingControl/Control")
        return self.muted

    def sonos_GetFavorites(self, favorite_type='R:0/0', start='0', max_items='10'):
        '''Gets the favorite radio stations (TuneIn), favorite radio shows or Sonos favorites (radio stations and libraries)
           Default is favorite radio stations from TuneIn, for radio shows choose R:0/1 as favorite_type
           and for Sonos favorites choose FV:2/0 as favorite_type
           the max_items 10 is due to the Domoticz limit of 10 items in a selector switch'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">\
                                        <ObjectID>' + favorite_type + '</ObjectID>\
                                        <BrowseFlag>BrowseDirectChildren</BrowseFlag>\
                                        <Filter>dc:title,res,dc:creator,upnp:artist,upnp:album,upnp:albumArtURI</Filter>\
                                        <StartingIndex>' + start + '</StartingIndex>\
                                        <RequestedCount>' + max_items + '</RequestedCount>\
                                        <SortCriteria/>\
                                    </u:Browse>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:ContentDirectory:1#Browse', "/MediaServer/ContentDirectory/Control")
        return

    def sonos_SetAVTransportURI(self, url, metadata=''):
        '''Set the URL or filename to be played'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                        <CurrentURI>' + html.escape(url) + '</CurrentURI>\
                                        <CurrentURIMetaData>' + html.escape(metadata) + '</CurrentURIMetaData>\
                                    </u:SetAVTransportURI>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI', "/MediaRenderer/AVTransport/Control")
        return

    def sonos_SetRadio(self, radio, name=''):
        '''Wrapper of SetAVTransporURI to set radio station including metadata'''
        metadata = '<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" \
                    xmlns:r="urn:schemas-rinconnetworks-com:metadata-1-0/" xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">\
                        <item id="R:0/0/0" parentID="R:0/0" restricted="true">\
                            <dc:title>' + name + '</dc:title>\
                            <upnp:class>object.item.audioItem.audioBroadcast</upnp:class>\
                            <desc id="cdudn" nameSpace="urn:schemas-rinconnetworks-com:metadata-1-0/">SA_RINCON65031_</desc>\
                        </item>\
                    </DIDL-Lite>'
        self.sonos_SetAVTransportURI(radio, metadata)
        return

    def sonos_SetCommand(self, command):
        '''Set the command, e.g. Play, Pause, Stop, Previous, Next'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:' + command + ' xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Speed>1</Speed>\
                                    </u:' + command + '>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#' + command + '', "/MediaRenderer/AVTransport/Control")
        return
    
    def sonos_SetMute(self, DesiredMute):
        '''Mute or unmute'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:SetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Channel>Master</Channel>\
                                        <DesiredMute>' + DesiredMute + '</DesiredMute>\
                                    </u:SetMute>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:RenderingControl:1#SetMute', "/MediaRenderer/RenderingControl/Control")
        return

    def sonos_SetVolume(self, mediaLevel):
        '''Set volume'''
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Channel>Master</Channel>\
                                        <DesiredVolume>' + mediaLevel +  '</DesiredVolume>\
                                    </u:SetVolume>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:RenderingControl:1#SetVolume', "/MediaRenderer/RenderingControl/Control")
        return

    def sonos_Seek(self, arg1, arg2=''):
        '''Seek track and time'''
        if arg2 == '':
            Unit = "REL_TIME"
            position = arg1
        else:
            Unit = arg1
            position = arg2
        self.sendMessage('<?xml version="1.0"?>\
                            <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\
                                <s:Body>\
                                    <u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">\
                                        <InstanceID>0</InstanceID>\
                                        <Unit>' + Unit + '</Unit>\
                                        <Target>' + position + '</Target>\
                                    </u:Seek>\
                                </s:Body>\
                            </s:Envelope>', 
                            'urn:schemas-upnp-org:service:AVTransport:1#Seek', "/MediaRenderer/AVTransport/Control")
        return
    ###### SONOS COMMANDS ######
        
_plugin = BasePlugin()

def onStart():
    _plugin.onStart()

def onCommand(Unit, Command, Level, Hue):
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onHeartbeat():
    _plugin.onHeartbeat()

# Update Device into database
def UpdateDevice(Unit, nValue, sValue, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if Unit in Devices:
        if Devices[Unit].nValue != nValue or Devices[Unit].sValue != sValue or AlwaysUpdate == True:
            Devices[Unit].Update(nValue, str(sValue))
            Domoticz.Log("Update " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "'")
    return

# Synchronise images to match parameter in hardware page
def UpdateImage(Unit):
    if Unit in Devices and Parameters["Mode2"] in Images:
        LogMessage("Device Image update: '" + Parameters["Mode2"] + "', Currently " + str(Devices[Unit].Image) + ", should be " + str(Images[Parameters["Mode2"]].ID))
        if Devices[Unit].Image != Images[Parameters["Mode2"]].ID:
            Devices[Unit].Update(nValue=Devices[Unit].nValue, sValue=str(Devices[Unit].sValue), Image=Images[Parameters["Mode2"]].ID)
    return

# xml built in parser threw import error on expat so just do it manually
def extractTagValue(tagName, XML):
    startPos = XML.find(tagName)
    endPos = XML.find(tagName, startPos+1)
    if startPos == -1 or endPos == -1: Domoticz.Error("'" + tagName + "' not found in supplied XML")
    return XML[startPos+len(tagName)+1:endPos-2]

# Check if value is a number
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

# Unescape HTML characters
def unescape(s):
    '''Unescape HTML characters, s as string'''
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&apos;", "'")
    s = s.replace('&quot;', '"')
    # this has to be last:
    s = s.replace("&amp;", "&")
    return s

# Generic helper functions
def LogMessage(Message):
    if Parameters["Mode6"] == "File":
        f = open(Parameters["HomeFolder"] + "plugin.log", "a")
        f.write(Message + "\r\n")
        f.close()
    Domoticz.Debug(Message)

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            LogMessage( "'" + x + "':'" + str(Parameters[x]) + "'")
    LogMessage("Device count: " + str(len(Devices)))
    for x in Devices:
        LogMessage("Device:           " + str(x) + " - " + str(Devices[x]))
        LogMessage("Internal ID:     '" + str(Devices[x].ID) + "'")
        LogMessage("External ID:     '" + str(Devices[x].DeviceID) + "'")
        LogMessage("Device Name:     '" + Devices[x].Name + "'")
        LogMessage("Device nValue:    " + str(Devices[x].nValue))
        LogMessage("Device sValue:   '" + Devices[x].sValue + "'")
        LogMessage("Device LastLevel: " + str(Devices[x].LastLevel))
    return

def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        LogMessage("HTTP Details ("+str(len(httpDict))+"):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                LogMessage("--->'"+x+" ("+str(len(httpDict[x]))+"):")
                for y in httpDict[x]:
                    LogMessage("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
            else:
                LogMessage("--->'" + x + "':'" + str(httpDict[x]) + "'")