# Sonos - Domoticz Python plugin
**Domoticz Python plugin for Sonos**

*This plugin can be used to control your Sonos from Domoticz.
Thanks to @tester22 for making the first [version](https://github.com/tester22/Domoticz-Sonos) which I used as an extensive basis for this plugin.*

## Table of Contents
- [Information](#information)
- [Sonos plugin instructions](#sonos-plugin-instructions)
  - [Domoticz settings](#domoticz-settings)
- [Notifications](#notifications)
- [Screenshots](#screenshots)

## Information
The plugin will show information from your Sonos and let's you control it in Domoticz.
There are four switches made when this plugin is used:

* Status switch: To switch on/off the Sonos and shows [Artist] - [Song] or [Radio station] - [Song] being played.

* Volume slider: To change the volume or (un)mute.

* Control selector: When a song is being played this can be used to go to Previous or Next song. Also a Pause and Play function.

* Radio favorites selector: Shows a dropdown list with a maximum of 10 radio stations from the My Radio Stations of Radio by TuneIn.

## Sonos plugin instructions
To get your Sonos IP you can go to Help, Info about my Sonos system on your Sonos Controller.

### Domoticz settings
See this [link](https://www.domoticz.com/wiki/Using_Python_plugins) for more information on the Domoticz plugins.
This plugin works with the old and new version of the Python framework in Domoticz.
* SSH to your server on which Domoticz is installed

* Enter the following commands
```bash
cd domoticz/plugins
git clone https://github.com/gerard33/sonos.git
```
  * *When updating to the latest version on Github enter the following commands*
  ```bash
  cd domoticz/plugins/sonos
  git pull
  ```

* Restart the Domoticz service
```bash
sudo service domoticz.sh restart
```

* Now go to **Setup**, **Hardware** in your Domoticz interface. There you add
**Sonos Players**.

Make sure you enter all the required fields.

| Field | Information|
| ----- | ---------- |
| IP address | Enter the IP address of your Sonos (see instructions above how to find the IP address, also make sure it is static) |
| Update interval | Enter the update interval in seconds (must be between 10 and 30 seconds) |
| Icon | You can choose between the standard Sonos icon or the icon of a Sonos 1 or Sonos 5 |
| Notifications | Set to True if you want to be able to play mp3 files on your Sonos which can be triggered with the Domoticz notification function |
| Notifications folder | This is the folder where the mp3 files are stored which can be used with the Notifications function. |
| | Prefered method is to make a folder 'notifications' in the www folder of Domoticz. This makes sure the plugin can check if the file exists and also the Sonos is able to play this file without setting any permissions. |
| | Example (always start with 'http://'): **http://<i></i>192.168.1.170:8080/notifications** |
| | Other method is to use a path to a network share on which the mp3 files are available. When you do this, make sure you have added this folder to the Sonos Library using this [link](https://sonos.custhelp.com/app/answers/detail/a_id/261/~/adding-and-updating-your-music-library). |
| | Example (always start with '//'): **//nas/music/notifications** |
| Refresh radio list | Set this to True to refresh the radio list in Domoticz with the list from the Sonos. This will mean the current switch in Domoticz is deleted and a new one is created with the Sonos radio station favorites. This will also mean that switch is put at the bottom of your switches in the Switches tab. |
| Debug | When set to True the plugin shows additional information in the Domoticz log. When set to Logging the plugin will also log all these data in the file plugin.log in the plugin folder. |

After clicking on the Add button the devices are available in the **Switches** tab.

## Notifications
When you have set Notifications to True and set a correct folder with notifications files (for example in mp3 format) you can use the builtin notification function of Domoticz.
This way you can let any Domoticz device generate a notification which, for which a mp3 file is played on your Sonos.

See the screenshot below how to set that up from the Domoticz GUI.
The format for the Custom Message field is: [filename]/[volume]
So 'message.mp3/30' means that message.mp3 (stored in the folder which you have set in the Notifications folder field) will be played with the volume set to 30.

Before playing the notification the plugin will first store what is currently played (song or radio station) and the volume.
After the notification is finished, the Sonos will either resume playing that song at the correct time or playing the radio station at the right volume.

It's also possible to send a notification to the Sonos using LUA. Below you will find an example.
The relevant part in '''commandArray['SendNotification']''' is '''message.mp3/30''' and '''sonos_kantoor'''. The other part between the #'s is not used, but leave at like that (at least the #'s)  to make sure the notification is correctly sent to Sonos.

```lua
commandArray = {}

if devicechanged['Test'] == 'Off' then
    commandArray['SendNotification']='message.mp3/30#body#0#sound#extradata#sonos_kantoor'
    print('Notification sent to Sonos kantoor')
end

return commandArray
```
## Screenshots
**Switches**

![sonos_screenprint](https://user-images.githubusercontent.com/11230573/28986875-2932200e-7969-11e7-99f3-baa63367ca16.png)

**Notification settings**

![sonos_screenprint_notification](https://user-images.githubusercontent.com/11230573/28987645-65e11958-796c-11e7-8a70-12541f92e2ef.png)







