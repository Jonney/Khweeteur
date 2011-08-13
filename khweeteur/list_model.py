#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright (c) 2010 Benoît HERVIER
# Copyright (c) 2011 Neal H. Walfield
# Licenced under GPLv3

'''A simple Twitter client made with pyqt4 : QModel'''

from __future__ import with_statement

import time
import cPickle as pickle
#import glob
import os

SCREENNAMEROLE = 20
REPLYTOSCREENNAMEROLE = 21
REPLYTEXTROLE = 22
REPLYIDROLE = 25
IDROLE = 23
ORIGINROLE = 24
TIMESTAMPROLE = 26
RETWEETOFROLE = 27
ISMEROLE = 28
PROTECTEDROLE = 28
USERIDROLE = 29
ISNEWROLE = 30

from PySide.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, QSettings
from PySide.QtGui import QPixmap
import twitter #Not really unused. Avoid pickle to do it each time

pyqtSignal = Signal

class KhweetsModel(QAbstractListModel):

    """ListModel : A simple list : Start_At,TweetId, Users Screen_name, Tweet Text, Profile Image"""

    dataChanged = pyqtSignal(QModelIndex, QModelIndex)

    def __init__(self):
        QAbstractListModel.__init__(self)

        # Cache the passed data list as a class member.

        self._items = {}
        self._uids = {}

        self._avatars = {}
        self.now = time.time()
        self.nothing_really_loaded = True
        self.call = 'HomeTimeLine'
        self.max_created_at = None
        self.new_message_horizon = self.now

        self._items[self.call] = []

    def __del__(self):
        if not self.nothing_really_loaded:
            settings = QSettings('Khertan Software', 'Khweeteur')
            settings.setValue(
                self.call + '-new-message-horizon', self.max_created_at)

    def setLimit(self, limit):
        self.khweets_limit = limit

    def getCacheFolder(self):
        return os.path.join(os.path.expanduser('~'), '.khweeteur', 'cache',
                            os.path.normcase(unicode(self.call.replace('/', '_'
                            ))).encode('UTF-8'))

    def rowCount(self, parent=QModelIndex()):
        return len(self._items[self.call][:self.khweets_limit])

    def refreshTimestamp(self):
        self.now = time.time()
        self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(0,
                              len(self._items)))

    def destroyStatus(self, index):
        self._items.pop(index.row())
        self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(0,
                              len(self._items)))

    def load(self, call, limit = None):
        """

        Returns whether the load loaded a new data set (True) or was
        just a reload (False).
        """
        self.now = time.time()

        # new_message_horizon is the points in time that separates read
        # messages from new messages.  The messages creation time is
        # used.
        settings = QSettings('Khertan Software', 'Khweeteur')
        if self.call != call:
            # It's not a reload.  Save the setting for the old stream
            # and load the setting for the new one.
            ret = True

            if not self.nothing_really_loaded:
                settings.setValue(
                    self.call + '-new-message-horizon', self.max_created_at)

            try:
                self.new_message_horizon = int(
                    settings.value(call + '-new-message-horizon', 0))
            except ValueError:
                self.new_message_horizon = self.now
        else:
            ret = False

        self.nothing_really_loaded = False

        self.call = call
        if call not in self._items:
            self._items[call] = []
            self._uids[call] = []

        self.avatar_path = os.path.join(os.path.expanduser('~'), '.khweeteur',
                                       'avatars')

        try:
            folder = self.getCacheFolder()

            uids = os.listdir(folder)
            if limit:
                uids.sort()
                uids.reverse()
                uids = uids[:limit]
            _uids = self._uids[call]
            _items = self._items[call]
            for uid in uids:
                if uid not in _uids:
                    with open(os.path.join(folder, str(uid)), 'rb') as pkl_file:
                        status = pickle.load(pkl_file)
                    _uids.append(uid)
                    _items.append(status)
                    if hasattr(status, 'user'):
                        if status.user.profile_image_url not in self._avatars:
                            profile_image = os.path.join(self.avatar_path,
                                os.path.basename(status.user.profile_image_url.replace('/', '_')))
                            try:
                                self._avatars[status.user.profile_image_url] = \
                                QPixmap(os.path.splitext(profile_image)[0] + '.png', 'PNG')
                            except:
                                self._avatars[status.user.profile_image_url] = QPixmap('/opt/usr/share/icons/hicolor/48x48/hildon/general_default_avatar.png')
                    else:
                        self._avatars['default'] = QPixmap('/opt/usr/share/icons/hicolor/48x48/hildon/general_default_avatar.png')


            _items.sort(key=lambda status: status.created_at_in_seconds,
                             reverse=True)
            _items = _items[:self.khweets_limit]
            _uids = _uids[:self.khweets_limit]

        except Exception, e:
            import traceback
            traceback.print_exc()
            print 'unSerialize : ', e

        self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(0,
                              len(self._items[call])))

        return ret

    def data(self, index, role=Qt.DisplayRole):
        if isinstance(index, int):
            status = self._items[self.call][index]
        else:
            status = self._items[self.call][index.row()]

        if role == Qt.DisplayRole:
            try:
                if status.truncated:
                    return status.retweeted_status.text
                else:
                    return status.text
            except:
                return status.text
        elif role == SCREENNAMEROLE:
            try:
                return self._items[self.call][index.row()].user.screen_name
            except:
                return self._items[self.call][index.row()].sender_screen_name
        elif role == IDROLE:
            return self._items[self.call][index.row()].id
        elif role == REPLYIDROLE:
            try:
                return self._items[self.call][index.row()].in_reply_to_status_id
            except:
                return None
        elif role == REPLYTOSCREENNAMEROLE:
            try:
                return self._items[self.call][index.row()].in_reply_to_screen_name
            except:
                return None
        elif role == REPLYTEXTROLE:
            return self._items[self.call][index.row()].in_reply_to_status_text
        elif role == ORIGINROLE:
            return self._items[self.call][index.row()].base_url
        elif role == RETWEETOFROLE:
            try:
                return self._items[self.call][index.row()].retweeted_status
            except:
                return None
        elif role == ISMEROLE:
            try:
                return self._items[self.call][index.row()].is_me
            except:
                return False
        elif role == TIMESTAMPROLE:

            return self._items[self.call][index.row()].GetRelativeCreatedAt(self.now)
        elif role == ISNEWROLE:
            try:
                created_at = int(status.GetCreatedAtInSeconds())
            except ValueError:
                created_at = 0
            self.max_created_at = max(self.max_created_at, created_at)

            return created_at > self.new_message_horizon
        elif role == PROTECTEDROLE:
            return self._items[self.call][index.row()].user.protected
        elif role == USERIDROLE:
            try:
                return self._items[self.call][index.row()].user.id
            except AttributeError:
                return self._items[self.call][index.row()].sender_id
        elif role == Qt.DecorationRole:
            try:
                return self._avatars[self._items[self.call][index.row()].user.profile_image_url]
            except:
                return self._avatars['default']
        else:
            return None

    def wantsUpdate(self):
        self.layoutChanged.emit()


