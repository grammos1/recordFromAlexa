import boto3
import json
import os
from datetime import datetime
import configparser
import urllib.request
import configparser
import sys
import shutil
import paramiko
from time import sleep
import ffmpy3
import vlc
pid = os.getpid()

def getSetting(section, setting):
    config = configparser.ConfigParser()
    config.read('settings.cfg')
    if section not in config.sections():
       # print("Section " + section + " not found. Will try DEFAULT")
        section = "DEFAULT"
    try:
        #print ("Setting " + setting + " to " + config[section][setting])
        return config[section][setting]
    except:
        print ("Key " + setting + " not found in section "+ section)

def toLog(message):
    f = open("recorder.log", "a+")
    f.write ("{" + str(pid) + "} :: " + str(datetime.now()) + " :: " + str(message) + str("\n"))
    f.close()


def recordMyShow(start, end, name):
    toLog("Starting now")
    stream = ""
    ocuser = ""
    ocpass = ""
    ocurl = ""
    ocbasedir = ""
    sshuser = ""
    sshpass = ""
    sshserver = ""
    sshpath = ""
    podcastrefreshurl = ""
    trimstart = 0
    savelocation = ""
    stream = getSetting(name.upper(), "stream")
    sshuser = getSetting(name.upper(), "user")
    sshpass = getSetting(name.upper(), "password")
    sshserver = getSetting(name.upper(), "server")
    sshpath = getSetting(name.upper(), "podcastpath")
    podcastrefreshurl = getSetting(name.upper(), "podcastrefreshurl")
    if sshuser == "" or sshpass == "" or sshserver == "" or podcastrefreshurl == "":
        print("You want to upload to podcast generator but settings in the config file are incomplete")
        print("Set the user, password, server, podcastpath and podcastrefreshurl key/values")
        print("Good bye")
        toLog("You want to upload to podcast generator but settings in the config file are incomplete")
    trimstart = int(getSetting(name.upper(), "trimstart"))
    now = datetime.now()
    end = datetime.strptime(str(endDateTime),"%Y-%m-%d %H:%M:%S")
    today = now.isoformat()
    today = str(today[:10]).replace("-", "")
    today = today[2:]
    today = today + "-" + now.strftime('%a')
    streamName = name
    filename = streamName + today + ".mp3"
    targetdir = "/" + streamName + "/" + str(now.year) + "/" + str(now.month) + " - " + str(now.strftime("%b"))
    print("Starting at " + str(now))
    print("Will stop at " + str(end))
    parameters = "sout=#transcode{acodec=mp3,channels=2,ab=64}:duplicate{dst=std{access=file,mux=raw,dst='" + filename + "'"
    toLog("Starting VLC")
    instance = vlc.Instance()
    player = instance.media_player_new()
    media = instance.media_new(stream, parameters)
    media.get_mrl()
    player.set_media(media)
    try:
        player.play()
    except:
        print("Cannot record from that stream")
        print("/OpensWindowAndJumpsOut")
        toLog("Cannot record from that stream")
        exit(2)
    recording = True
    while recording:
        now = datetime.now()
        if str(player.get_state()) == "State.Ended":
            print("Cannot record from that stream or connection lost")
            toLog("Lost Connection")
            break
        if now > end:
            player.stop()
            print("OK. We are done recording")
            toLog("Finished capturing Stream")
            break

    try:
        toLog("Manhandling the MP3 file")
        tempfilename = filename.replace(".mp3", "a.mp3")
        os.replace(filename, tempfilename)
        artist = streamName
        genre = "radio"
        album = streamName
        title = filename.replace(".mp3", "")
        ff = ffmpy3.FFmpeg(inputs={tempfilename: None}, outputs={filename: '-acodec copy -ss 00:02:00 -metadata title='+str(title)+' -metadata artist=' + str(artist)+' -metadata genre=' + str(genre)+' -metadata album=' + str(album)})
        ff.run()
    except Exception as e:
        print("FFMPeg failed to load, trim, or enrich a valid audio file")
        toLog("FFMPeg failed to load, trim, or enrich a valid audio file")
        toLog(str(e))
        exit(2)
    print ("Uploading file to podcast")
    try:
        toLog("Uploading over SSH")
        ssh = paramiko.SSHClient()
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(sshserver, username=sshuser, password=sshpass)
        sftp = ssh.open_sftp()
        sftp.put(filename, sshpath + filename)
        sftp.close()
        ssh.close()
    except Exception as e:
        toLog("Failed to upload")
        toLog(str(e))
    print ("Refreshing Podcasts")
    contents = urllib.request.urlopen(podcastrefreshurl).read()
    print("Deleting local files")
    os.remove(filename)
    os.remove(tempfilename)
    exit(0)

    return True

session = boto3.session.Session(profile_name='pyRecordRadio')
s3 = session.resource('s3')
localfilename = "temp.json"
recorderTriggerBucket = s3.Bucket('gr-recordertrigger')
for files in recorderTriggerBucket.objects.filter(Prefix=""):
    print (files.key)
    localfilename = str(files.key)
    recorderTriggerBucket.download_file(files.key, localfilename)
    localfile = open(localfilename, "r")
    data = localfile.read()
    localfile.close()
    #print (data)
    data = data.replace('\'','"')
    data = json.loads(data)
    startDateTime = datetime.strptime(data['startDateTime'],"%Y-%m-%d %H:%M:%S")
    endDateTime = datetime.strptime(data['endDateTime'],"%Y-%m-%d %H:%M:%S")
    name = (data['Name'])
    print ("For file " + files.key)
    startsInFuture = startDateTime > datetime.now()
    endsInPast = endDateTime < datetime.now()
    print ("\t Start Date " + str(startDateTime) + " being in the future is " + str(startsInFuture))
    print("\t Finish Date " + str(endDateTime) + " being overdue is " + str(endsInPast))
    if not startsInFuture:
        s3.Object('gr-recordertrigger',files.key).delete()
        os.remove(localfilename)
        recordMyShow(startDateTime, endDateTime, name)
    if startsInFuture:
        os.remove(localfilename)






    #teststring = "{'DEFAULT': {'startDateTime': '2018-12-20 23:33:00', 'endDateTime': '2018-12-20 23:43:00', 'Name': 'panatha'}}"
    #config = configparser.ConfigParser()
    #config.read_string(teststring)





