# Copyright (C) 2011-2015  Edward G. Bruck <ed.bruck1@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.   

import pickle
import urllib.request, urllib.parse, urllib.error
import os
import time
import redis
import socket

REDIS_SERVER="redis"
REDIS_PORT=6379
REDIS_TIMEOUT=10
RB_PODCAST_POS_SAVE_INTERVAL=60
MAX_FILE_LIST=256

from gi.repository import GObject, Peas 
from gi.repository import RB

class PodcastPos(GObject.Object, Peas.Activatable):
    __gtype_name__ = 'PodcastPosPlugin'

    object = GObject.property (type = GObject.Object)

    def __init__(self):
        GObject.Object.__init__(self)

        self.data_file = os.path.expanduser("~") + "/.rb-podcast-pos"
        
        self.last_update = int(time.time())

        try:
            redis_conn = redis.Redis(REDIS_SERVER, socket_timeout=REDIS_TIMEOUT, port=REDIS_PORT)
            self.pos_dict = pickle.loads(redis_conn.get("rb-podcast-pos"))
        except:
            try:
                self.pos_dict = pickle.load(open(self.data_file, 'rb'))
            except:
                self.pos_dict = {}

    def purge_missing_and_save(self):
        if len(self.pos_dict) >= MAX_FILE_LIST:
            to_purge = []
            for key in self.pos_dict:
                if not os.path.isfile(urllib.parse.unquote(key[7:])):
                    to_purge.append(key)

                    for key in to_purge:
                        del self.pos_dict[key]
            
        self.save_podcast_pos()

    def do_activate(self):        
        shell = self.object        
        shell_player  = shell.props.shell_player
        
        self.db = shell.props.db
        self.psc_id1 = shell_player.connect('playing-song-changed', self.playing_song_changed)
        self.psc_id2 = shell_player.connect('elapsed-changed', self.elapsed_changed)        

    def get_song_info(self, entry):
        song = {
            "genre"    : entry.get_string(RB.RhythmDBPropType.GENRE),  
            "duration" : entry.get_ulong(RB.RhythmDBPropType.DURATION),
            "location" : entry.get_playback_uri()
        }
        return song

    def do_deactivate(self):
        self.purge_missing_and_save()

        shell = self.object        
        self.psc_id1 = None
        self.psc_id2 = None
        self.db = None

    def playing_song_changed(self, player, entry):       
        if entry:
            song_info = self.get_song_info(entry)
            if song_info['location'] in self.pos_dict:                
                new_pos = self.pos_dict[song_info['location']]
                
                if new_pos >= song_info['duration']-1:
                    return
                
                # I'm sure there is a better way...
                n=0
                while(n<10):
                    try:
                        player.set_playing_time(new_pos)
                        break
                    except:
                        time.sleep(0.1)
                        ++n

    def elapsed_changed(self, player, pos):
        if pos > 0:
            entry = player.get_playing_entry()

            if entry:
                song_info = self.get_song_info(entry)
                if "Podcast" == song_info['genre']:
                    self.pos_dict[song_info['location']] = pos

                    if  int(time.time()) - self.last_update >= RB_PODCAST_POS_SAVE_INTERVAL:
                        self.save_podcast_pos()                       

    def save_podcast_pos(self):
        pickle_data = pickle.dumps(self.pos_dict)
        open(self.data_file, 'wb').write(pickle_data)

        try:
            redis_conn = redis.Redis(REDIS_SERVER, socket_timeout=REDIS_TIMEOUT, port=REDIS_PORT)
            redis_conn.set("rb-podcast-pos", pickle_data)
            redis_conn.set("rb-podcast-pos-timestamp", socket.gethostname() + "@" + time.strftime("%c") +", " + str(len(self.pos_dict)))
        except:
            pass

        self.last_update = int(time.time())
