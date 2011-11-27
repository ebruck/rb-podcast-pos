# -*- coding: utf8 -*-
# 
# Copyright (C) 2011  Edward G. Bruck <ed.bruck1@gmail.com>
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
import os

from gi.repository import GObject, Peas 
from gi.repository import RB

class PodcastPos(GObject.Object, Peas.Activatable):
    __gtype_name__ = 'PodcastPosPlugin'

    object = GObject.property (type = GObject.Object)

    def __init__(self):
        GObject.Object.__init__(self)

        self.data_file = os.path.expanduser("~") + "/.rb-podcast-pos"
        
        try:
            self.pos_dict = pickle.load(open(self.data_file, 'rb'))
        except:
            self.pos_dict = {}

    def purge_missing(self):
        to_purge = []
        for key in self.pos_dict:
            if not self.db.entry_lookup_by_location(key):
                to_purge.append(key)

        for key in to_purge:
            del self.pos_dict[key]

    def do_activate(self):        
        shell = self.object        
        shell_player  = shell.props.shell_player
        
        self.db = db = shell.props.db
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
        self.purge_missing()

        shell = self.object        
        shell.get_player().disconnect(self.psc_id1)
        shell.get_player().disconnect(self.psc_id2)
        self.psc_id1 = None
        self.psc_id2 = None
        self.db = None

        pickle.dump(self.pos_dict, open(self.data_file, 'wb'))       

    def playing_song_changed(self, player, entry):       
        if entry:
            song_info = self.get_song_info(entry)
            if self.pos_dict.has_key(song_info['location']):                
                new_pos = self.pos_dict[song_info['location']]
                
                if new_pos >= song_info['duration']-1:
                    return

                player.set_playing_time(new_pos)

    def elapsed_changed(self, player, pos):
        if pos > 0:
            entry = player.get_playing_entry()

            if entry:
                song_info = self.get_song_info(entry)
                if "Podcast" == song_info['genre']:
                    self.pos_dict[song_info['location']] = pos
