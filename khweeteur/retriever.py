#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2010 Benoît HERVIER
# Copyright (c) 2011 Neal H. Walfield
# Licenced under GPLv3

from __future__ import with_statement

import sys
import twitter
import socket
socket.setdefaulttimeout(60)
from urllib import urlretrieve

import cPickle as pickle
try:
    from PIL import Image
except ImportError:
    import Image

from PySide.QtCore import QSettings,QThread, Signal

#from threading import Thread

import logging
import os
import socket

class KhweeteurRefreshWorker(QThread):

    new_tweets = Signal(int, str)
    error = Signal(str)

    def __init__(
        self,
        api,
        call,
        #dbus_handler,
        me_user_id,
        ):
        """
        api: An instance of the twitter.Api class.

        call is one of

          'HomeTimeline': Fetch the home time line
          'Mentions': Fetch user mentions
          'DMs': Fetch direct messages
          'Search:*': Fetch search results where * is the terms to search for
          'RetrieveLists': Retrive lists
          'List:*:*': The first * should be replace with the user and
                      the second with the id
          'Near:*:*': Fetch tweets near (1km) a the specified
                      location.  The first start is the the first
                      geocode and the second * is the second geocode.

        me_user_id: The user's user id.
        """
        QThread.__init__(self)
        self.api = api

        self.me_user_id = me_user_id
        self.call = call
        #self.dbus_handler = dbus_handler
        socket.setdefaulttimeout(60)

#    def send_notification(self, msg, count):
#        try:
#            #self.dbus_handler.new_tweets(count, msg)
#            self.new_tweets.emit(count, msg)
#        except Exception, err:
#            logging.debug('Retriever : %s' % str(err))

    def getCacheFolder(self):
        if not hasattr(self, 'folder_path'):
            self.folder_path = os.path.join(os.path.expanduser('~'),
                    '.khweeteur', 'cache',
                    os.path.normcase(unicode(self.call.replace('/', '_'
                    ))).encode('UTF-8'))

            if not os.path.isdir(self.folder_path):
                try:
                    os.makedirs(self.folder_path)
                except IOError, e:
                    logging.debug('getCacheFolder:' + e)

        return self.folder_path

    def downloadProfilesImage(self, statuses):
        avatar_path = os.path.join(os.path.expanduser('~'), '.khweeteur',
                                   'avatars')
        if not os.path.exists(avatar_path):
            os.makedirs(avatar_path)

        for status in statuses:
            if type(status) != twitter.DirectMessage:
                cache = os.path.join(avatar_path,
                                     os.path.basename(status.user.profile_image_url.replace('/'
                                     , '_')))
                if not os.path.exists(cache):
                    try:
                        urlretrieve(status.user.profile_image_url, cache)
                        im = Image.open(cache)
                        im = im.resize((50, 50))
                        im.save(os.path.splitext(cache)[0] + '.png', 'PNG')
                    except StandardError, err:
                        logging.debug('DownloadProfilImage:' + str(err))

    def removeAlreadyInCache(self, statuses):
        """
        Delete the file associated with the statuses.

        statuses is a list of status updates (twitter.Status objects).
        """
        # Load cached statuses

        try:
            folder_path = self.getCacheFolder()
            for status in statuses:
                if os.path.exists(os.path.join(folder_path, str(status.id))):
                    statuses.remove(status)
                    logging.debug('%s found in cache (%s)' % (str(status.id),
                                  folder_path))
                else:
                    logging.debug('%s not found in cache (%s)'
                                  % (str(status.id), folder_path))
        except StandardError, err:
            logging.debug(err)

    def applyOrigin(self, statuses):
        """
        Set the statuses origin (the account from which the status was
        fetch).

        statuses is a list of status updates (twitter.Status objects).
        """
        for status in statuses:
            status.base_url = (
                self.api.base_url + ';' + self.api._access_token_key)

    def getOneReplyContent(self, tid):

        # Got from cache

        status = None
        for (root, dirs, files) in os.walk(os.path.join(os.path.expanduser('~'
                ), '.khweeteur', 'cache')):
            for afile in files:
                if unicode(tid) == afile:
                    try:
                        with open(os.path.join(root, afile), 'rb') as fhandle:
                            status = pickle.load(fhandle)
                        return status.text
                    except StandardError, err:
                        logging.debug('getOneReplyContent:' + err)

        try:
            rpath = os.path.join(os.path.expanduser('~'), '.khweeteur', 'cache'
                                 , 'Replies')
            if not os.path.exists(rpath):
                os.makedirs(rpath)

            status = self.api.GetStatus(tid)
            with open(os.path.join(os.path.join(rpath, unicode(status.id))),
                      'wb') as fhandle:
                pickle.dump(status, fhandle, pickle.HIGHEST_PROTOCOL)
            return status.text
        except StandardError, err:
            logging.debug('getOneReplyContent:' + str(err))

    def isMe(self, statuses):
        """
        statuses is a list of status updates (twitter.Status objects).
        For each status update, sets status.is_me according to whether
        the status's user id is the user's id.
        """
        for status in statuses:
            if status.user.id == self.me_user_id:
                status.is_me = True
            else:
                status.is_me = False

    def getRepliesContent(self, statuses):
        for status in statuses:
            try:
                if not hasattr(status, 'in_reply_to_status_id'):
                    status.in_reply_to_status_text = None
                elif not status.in_reply_to_status_text \
                    and status.in_reply_to_status_id:
                    status.in_reply_to_status_text = \
                        self.getOneReplyContent(status.in_reply_to_status_id)
            except StandardError, err:
                logging.debug('getOneReplyContent:' + err)

    def serialize(self, statuses):
        """
        statuses is a list of status updates (twitter.Status objects).
        For each status update, writes the status update to disk.
        """
        folder_path = self.getCacheFolder()

        for status in statuses:
            try:
                with open(os.path.join(folder_path, unicode(status.id)),
                          'wb') as fhandle:
                    pickle.dump(status, fhandle, pickle.HIGHEST_PROTOCOL)
            except:
                logging.debug('Serialization of %s failed: %s'
                              % (status.id, str (sys.exc_info()[0])))

    def run(self):
        settings = QSettings('Khertan Software', 'Khweeteur')
        statuses = []

        logging.debug('Thread Running')
        try:
            since = settings.value(self.api._access_token_key + '_' + self.call)

            if self.call == 'HomeTimeline':
                logging.debug('%s running' % self.call)
                statuses = self.api.GetHomeTimeline(since_id=since)
                logging.debug('%s finished' % self.call)
            elif self.call == 'Mentions':
                logging.debug('%s running' % self.call)
                statuses = self.api.GetMentions(since_id=since)
                logging.debug('%s finished' % self.call)
            elif self.call == 'DMs':
                logging.debug('%s running' % self.call)
                statuses = self.api.GetDirectMessages(since_id=since)
                logging.debug('%s finished' % self.call)
            elif self.call.startswith('Search:'):
                logging.debug('%s running' % self.call)
                statuses = self.api.GetSearch(since_id=since,
                        term=self.call.split(':', 1)[1])
                logging.debug('%s finished' % self.call)
            elif self.call == 'RetrieveLists':
                logging.debug('%s running' % self.call)

                # Get the list subscriptions

                lists = \
                    self.api.GetSubscriptions(user=self.api.VerifyCredentials().id)
                settings.beginWriteArray('lists')
                for (index, list_instance) in enumerate(lists):
                    settings.setArrayIndex(index)
                    settings.setValue('id', list_instance.id)
                    settings.setValue('user', list_instance.user.screen_name)
                    settings.setValue('name', list_instance.name)
                settings.endArray()

                # Get the status of list

                logging.debug('%s finished' % self.call)
                settings.sync()
            elif self.call.startswith('List:'):
                logging.debug('%s running' % self.call)
                user, id = self.call.split(':', 2)[1:]
                statuses = self.api.GetListStatuses(user=user, id=id,
                                                    since_id=since)
                logging.debug('%s finished' % self.call)

            #Near GPS
            elif self.call.startswith('Near:'):
                logging.debug('%s running' % self.call)
                geocode = self.call.split(':', 2)[1:] + ['1km']
                logging.debug('geocode=(%s)', str(geocode))
                statuses = self.api.GetSearch(since_id=since,
                        term='', geocode=geocode)
                logging.debug('%s finished' % self.call)
            else:
                logging.error('Unknown call : %s' % (self.call, ))
        except Exception, err:
            raise
            logging.debug('Retriever : %s' % str(err))
            try:
                if settings.contains('ShowInfos'):
                    if settings.value('ShowInfos') == '2':
                        self.error.emit('Khweeteur Error : %s' % str(err))
                        #self.dbus_handler.info('Khweeteur Error : ' + str(err))
            except Exception, err:
                raise
                logging.debug('Retriever : %s' % (str(err)))

        self.removeAlreadyInCache(statuses)
        if len(statuses) > 0:
            logging.debug('%s start download avatars' % self.call)
            self.downloadProfilesImage(statuses)
            logging.debug('%s start applying origin' % self.call)
            self.applyOrigin(statuses)
            logging.debug('%s start getreply' % self.call)
            self.getRepliesContent(statuses)
            if self.call != 'DMs':
                logging.debug('%s start isMe' % self.call)
                self.isMe(statuses)
            logging.debug('%s start serialize' % self.call)
            self.serialize(statuses)
            statuses.sort(reverse=True)
            settings.setValue(self.api._access_token_key + '_' + self.call,
                              statuses[0].id)
            self.new_tweets.emit(len(statuses), self.call)
        settings.sync()
        logging.debug('%s refreshed' % self.call)


