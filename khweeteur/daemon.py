#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2010 Benoît HERVIER
# Copyright (c) 2011 Neal H. Walfield
# Licenced under GPLv3

from __future__ import with_statement

import sys
import time
from PySide.QtCore import QSettings, Slot, QTimer, QCoreApplication
import atexit
import os
from signal import SIGTERM

import logging

from retriever import KhweeteurRefreshWorker
from settings import SUPPORTED_ACCOUNTS

import cPickle as pickle
import re

from qwidget_gui import __version__

import dbus

import dbus.mainloop.glib

#from dbus.mainloop.qt import DBusQtMainLoop
#DBusQtMainLoop(set_as_default=True)

import twitter
import glob

try:
    from PIL import Image
except:
    import Image

import os.path
import dbus.service

try:
    from QtMobility.Location import QGeoPositionInfoSource
except:
    print 'Pyside QtMobility not installed or broken'

# A hook to catch errors

def install_excepthook(version):
    '''Install an excepthook called at each unexcepted error'''

    __version__ = version

    def my_excepthook(exctype, value, tb):
        '''Method which replace the native excepthook'''

        # traceback give us all the errors information message like
        # the method, file line ... everything like
        # we have in the python interpreter

        import traceback
        trace_s = ''.join(traceback.format_exception(exctype, value, tb))
        print 'Except hook called : %s' % trace_s
        formatted_text = '%s Version %s\nTrace : %s' % ('Khweeteur',
                __version__, trace_s)
        logging.error(formatted_text)

    sys.excepthook = my_excepthook

_settings = None
_settings_synced = None
def settings_db():
    """
    Return the setting's database, a QSettings instance, ensuring that
    it is sufficiently up to date.
    """
    global _settings
    global _settings_synced

    if _settings is None:
        # First time through.
        _settings = QSettings('Khertan Software', 'Khweeteur')
        _settings_synced = time.time()
        return _settings

    # Ensure that the in-memory settings database is synchronized
    # with the values on disk.
    now = time.time()
    if now - _settings_synced > 10:
        # Last synchronized more than 10 seconds ago.
        _settings.sync()
        _settings_synced = now

    return _settings

class Daemon(object):

    """
    A generic daemon class.
    Usage: subclass the Daemon class and override the run() method
    """

    def __init__(
        self,
        pidfile,
        stdin='/dev/null',
        stdout='/dev/null',
        stderr='/dev/null',
        ):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """

        try:
            pid = os.fork()
            if pid > 0:

                # exit first parent

                sys.exit(0)
        except OSError, e:
            sys.stderr.write('fork #1 failed: %d (%s)\n' % (e.errno,
                             e.strerror))
            sys.exit(1)

        # decouple from parent environment

        os.chdir('/')
        os.setsid()
        os.umask(0)

        # do second fork

        try:
            pid = os.fork()
            if pid > 0:

                # exit from second parent

                sys.exit(0)
        except OSError, e:
            sys.stderr.write('fork #2 failed: %d (%s)\n' % (e.errno,
                             e.strerror))
            sys.exit(1)

        # redirect standard file descriptors

        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile

        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write('%s\n' % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def startfromprefs(self):
        settings = settings_db()
        if settings.contains('useDaemon'):
            if settings.value('useDaemon') == '2':
                self.start()

    def start(self):
        """
        Start the daemon
        """
        # Check for a pidfile to see if the daemon already runs
        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if pid:
            try:
                os.kill(pid, 0)
                message = 'pidfile %s already exist. Daemon already running?\n'
                sys.stderr.write(message % self.pidfile)
                sys.exit(1)
            except OSError:
                sys.stderr.write('pidfile %s already exist. But daemon is dead.\n'
                                  % self.pidfile)

        # Start the daemon

        self.daemonize()
        self.run()

    def debug(self):
        self.run()
        
    def stop(self):
        """
        Stop the daemon
        """

        # Get the pid from the pidfile

        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = 'pidfile %s does not exist. Daemon not running?\n'
            sys.stderr.write(message % self.pidfile)
            return   # not an error in a restart

        # Try killing the daemon process

        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find('No such process') > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                logging.error(str(err))
                sys.exit(1)

    def restart(self):
        """
        Restart the daemon
        """

        self.stop()
        self.start()

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """


class KhweeteurDBusHandler(dbus.service.Object):

    def __init__(self):
        dbus.service.Object.__init__(self, dbus.SessionBus(),
                                     '/net/khertan/Khweeteur')
        self.m_id = 0

    def info(self, message):
        '''Display an information banner'''

        logging.debug('Dbus.info(%s)' % message)

        message = message.replace('\'', '')
        message = message.replace('<', '')
        message = message.replace('>', '')

        if message == '':
            import traceback
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            logging.error('Null info message : %s'
                          % repr(traceback.format_exception(exc_type,
                          exc_value, exc_traceback)))

        try:
            m_bus = dbus.SystemBus()
            m_notify = m_bus.get_object('org.freedesktop.Notifications',
                                        '/org/freedesktop/Notifications')
            iface = dbus.Interface(m_notify, 'org.freedesktop.Notifications')
            if not message.startswith('Khweeteur'):
                message = 'Khweeteur : ' + message
            iface.SystemNoteInfoprint(message)
        except:
            import traceback
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            logging.error('Error info message : %s'
                          % repr(traceback.format_exception(exc_type,
                          exc_value, exc_traceback)))

    @dbus.service.method(dbus_interface='net.khertan.Khweeteur',
                         in_signature='', out_signature='b')
    def isRunning(self):
        return True
        
    @dbus.service.signal(dbus_interface='net.khertan.Khweeteur', signature='')
    def refresh_ended(self):
        pass

    @dbus.service.signal(dbus_interface='net.khertan.Khweeteur', signature='us')
    def new_tweets(self, count, ttype):
        logging.debug('New tweet notification ttype : %s (%s)' % (ttype,
                      str(type(ttype))))
        settings = settings_db()
        #.value('showNotifications') == '2':                      

        if ((ttype == 'Mentions') and
            (settings.value('showDMNotifications') == '2')) \
            or ((ttype == 'DMs') and
                (settings.value('showDMNotifications') == '2')):
            m_bus = dbus.SystemBus()
            m_notify = m_bus.get_object('org.freedesktop.Notifications',
                                        '/org/freedesktop/Notifications')
            iface = dbus.Interface(m_notify, 'org.freedesktop.Notifications')

            if ttype == 'DMs' :
                msg = 'New DMs'
            elif ttype == 'Mentions':
                msg = 'New mentions'
            else:
                msg = 'New tweets'
            try:
                self.m_id = iface.Notify(
                    'Khweeteur',
                    self.m_id,
                    'khweeteur',
                    msg,
                    msg,
                    ['default', 'call'],
                    {
                        'category': 'khweeteur-new-tweets',
                        'desktop-entry': 'khweeteur',
                        'dbus-callback-default'
                            : 'net.khertan.khweeteur /net/khertan/khweeteur net.khertan.khweeteur show_now'
                            ,
                        'count': count,
                        'amount': count,
                        },
                    -1,
                    )
            except:
                pass


class KhweeteurDaemon(Daemon,QCoreApplication):

    def __init__(self, pidfile,
        stdin='/dev/null',
        stdout='/dev/null',
        stderr='/dev/null',):
        Daemon.__init__(self,pidfile,stdin=stdin, \
                        stdout=stdout, \
                        stderr=stderr)
    def run(self):
        QCoreApplication.__init__(self,sys.argv)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        try:
            from PySide import __version_info__ as __pyside_version__
        except:
            __pyside_version__ = None
        try:
            from PySide.QtCore import __version_info__ as __qt_version__
        except:
            __qt_version__ = None

#        app = QCoreApplication(sys.argv)

        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(levelname)-8s %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename=os.path.expanduser('~/.khweeteur.log'), filemode='w')
        logging.info('Starting daemon %s' % __version__)
        logging.info('PySide version %s' % repr(__pyside_version__))
        logging.info('Qt Version %s' % repr(__qt_version__))

        try:
            os.nice(10)
        except:
            pass
            
        self.bus = dbus.SessionBus()
        self.bus.add_signal_receiver(self.update, path='/net/khertan/Khweeteur'
                                     , dbus_interface='net.khertan.Khweeteur',
                                     signal_name='require_update')
        self.bus.add_signal_receiver(self.post_tweet,
                                     path='/net/khertan/Khweeteur',
                                     dbus_interface='net.khertan.Khweeteur',
                                     signal_name='post_tweet')
        self.threads = []  # Here to avoid gc
        self.me_users = {}
        self.apis = {}
        self.idtag = None

        #On demand geoloc
        self.geoloc_source = None
        self.geoloc_coordinates = None

        # Cache Folder

        self.cache_path = os.path.join(os.path.expanduser('~'), '.khweeteur',
                                       'cache')
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

        # Post Folder

        self.post_path = os.path.join(os.path.expanduser('~'), '.khweeteur',
                                      'topost')
        if not os.path.exists(self.post_path):
            os.makedirs(self.post_path)

        self.dbus_handler = KhweeteurDBusHandler()
                
        # mainloop = DBusQtMainLoop(set_as_default=True)

        settings = settings_db()
        if not settings.contains('refresh_interval'):
            refresh_interval = 600
        else:
            refresh_interval = int(settings.value('refresh_interval')) * 60

        self.utimer = QTimer()
        self.utimer.timeout.connect(self.update)
        self.utimer.start(refresh_interval * 1000)
                
        QTimer.singleShot(200, self.update)

        # gobject.timeout_add_seconds(refresh_interval, self.update, priority=gobject.PRIORITY_LOW)

        logging.debug('Timer added')
        self.exec_()
        logging.debug('Daemon stop')

    def post_tweet(
        self,
        shorten_url=True,
        serialize=True,
        text='',
        latitude='',
        longitude='',
        base_url='',
        action='',
        tweet_id='',
        ):

        if not os.path.isdir(self.post_path):
            try:
                os.makedirs(self.post_path)
            except IOError, e:
                logging.debug('post_tweet:' + e)

        with open(os.path.join(self.post_path, str(time.time())), 'wb') as \
            fhandle:
            post = {
                'shorten_url': shorten_url,
                'serialize': serialize,
                'text': text,
                'latitude': latitude,
                'longitude': longitude,
                'base_url': base_url,
                'action': action,
                'tweet_id': tweet_id,
                }
            logging.debug('%s' % (post.__repr__(), ))
            pickle.dump(post, fhandle, pickle.HIGHEST_PROTOCOL)

#        self.do_posts() #Else we loop when action create a post

    def get_api(self, account):
        api = twitter.Api(username=account['consumer_key'],
                          password=account['consumer_secret'],
                          access_token_key=account['token_key'],
                          access_token_secret=account['token_secret'],
                          base_url=account['base_url'])
        api.SetUserAgent('Khweeteur')

        return api

    def geolocStart(self):
        '''Start the GPS with a 50000 refresh_rate'''
        self.geoloc_coordinates = None
        if self.geoloc_source is None:
            try:
                self.geoloc_source = \
                    QGeoPositionInfoSource.createDefaultSource(None)
            except:
                self.geoloc_source = None
                self.geoloc_coordinates = (0,0)
                print 'PySide QtMobility not installed or package broken'
            if self.geoloc_source is not None:
                self.geoloc_source.setUpdateInterval(50000)
                self.geoloc_source.positionUpdated.connect(self.geolocUpdated)
                self.geoloc_source.startUpdates()

    def geolocStop(self):
        '''Stop the GPS'''

        self.geoloc_coordinates = None
        if self.geoloc_source is not None:
            self.geoloc_source.stopUpdates()
            self.geoloc_source = None

    def geolocUpdated(self, update):
        '''GPS Callback on update'''

        if update.isValid():
            self.geoloc_coordinates = (update.coordinate().latitude(),
                                       update.coordinate().longitude())
            self.update()
            self.geolocStop()
        else:
            print 'GPS Update not valid'

    def do_posts(self):
        settings = settings_db()
        accounts = []

        nb_accounts = settings.beginReadArray('accounts')
        for index in range(nb_accounts):
            settings.setArrayIndex(index)
            accounts.append(dict((key, settings.value(key)) for key in
                            settings.allKeys()))
        settings.endArray()

        logging.debug('Number of account : %s' % len(accounts))

        items = glob.glob(os.path.join(self.post_path, '*'))

        if len(items)>0:
            if (settings.value('useGPS')=='2') and (settings.value('useGPSOnDemand')=='2'):
                if self.geoloc_source == None:
                    self.geolocStart()
                if self.geoloc_coordinates == None:
                    return

        for item in items:
            logging.debug('Try to post %s' % (item, ))
            try:
                with open(item, 'rb') as fhandle:
                    post = pickle.load(fhandle)
                    text = post['text']
                    if post['shorten_url'] == 1:
                        urls = re.findall("(?P<url>https?://[^\s]+)", text)
                        if len(urls) > 0:
                            import bitly
                            a = bitly.Api(login='pythonbitly',
                                    apikey='R_06871db6b7fd31a4242709acaf1b6648')

                            for url in urls:
                                try:
                                    short_url = a.shorten(url)
                                    text = text.replace(url, short_url)
                                except:
                                    pass

                    if (settings.value('useGPS')=='2') and (settings.value('useGPSOnDemand')=='2'):
                        post['latitude'], post['longitude'] = \
                            self.geoloc_coordinates

                    if not post['latitude']:
                        post['latitude'] = None
                    else:
                        post['latitude'] = int(post['latitude'])
                    if not post['longitude']:
                        post['longitude'] = None
                    else:
                        post['longitude'] = int(post['longitude'])

                    # Loop on accounts

                    for account in accounts:

                        # Reply

                        if post['action'] == 'reply':  # Reply tweet
                            if account['base_url'] == post['base_url'] \
                                and account['use_for_tweet'] == 'true':
                                api = self.get_api(account)
                                if post['serialize'] == 1:
                                    api.PostSerializedUpdates(text,
                                            in_reply_to_status_id=int(post['tweet_id'
                                            ]), latitude=post['latitude'],
                                            longitude=post['longitude'])
                                else:
                                    api.PostUpdate(text,
                                            in_reply_to_status_id=int(post['tweet_id'
                                            ]), latitude=post['latitude'],
                                            longitude=post['longitude'])
                                logging.debug('Posted reply %s : %s' % (text,
                                        post['tweet_id']))
                                if settings.contains('ShowInfos'):
                                    if settings.value('ShowInfos') == '2':
                                        self.dbus_handler.info('Khweeteur: Reply posted to '
                                         + account['name'])
                        elif post['action'] == 'retweet':

                            # Retweet

                            if account['base_url'] == post['base_url'] \
                                and account['use_for_tweet'] == 'true':
                                api = self.get_api(account)
                                api.PostRetweet(tweet_id=int(post['tweet_id']))
                                logging.debug('Posted retweet %s'
                                        % (post['tweet_id'], ))
                                if settings.contains('ShowInfos'):
                                    if settings.value('ShowInfos') == '2':
                                        self.dbus_handler.info('Khweeteur: Retweet posted to '
                                             + account['name'])
                        elif post['action'] == 'tweet':

                            # Else "simple" tweet

                            if account['use_for_tweet'] == 'true':
                                api = self.get_api(account)
                                if post['serialize'] == 1:
                                    api.PostSerializedUpdates(text,
                                            latitude=post['latitude'],
                                            longitude=post['longitude'])
                                else:
                                    api.PostUpdate(text,
                                            latitude=post['latitude'],
                                            longitude=post['longitude'])
                                logging.debug('Posted %s' % (text, ))
                                if settings.contains('ShowInfos'):
                                    if settings.value('ShowInfos') == '2':
                                        self.dbus_handler.info('Khweeteur: Status posted to '
         + account['name'])
                        elif post['action'] == 'delete':
                            if account['base_url'] == post['base_url']:
                                api = self.get_api(account)
                                api.DestroyStatus(int(post['tweet_id']))
                                path = os.path.join(os.path.expanduser('~'),
                                        '.khweeteur', 'cache', 'HomeTimeline',
                                        post['tweet_id'])
                                os.remove(path)
                                logging.debug('Deleted %s' % (post['tweet_id'],
                                        ))
                                if settings.contains('ShowInfos'):
                                    if settings.value('ShowInfos') == '2':
                                        self.dbus_handler.info('Khweeteur: Status deleted on '
         + account['name'])
                        elif post['action'] == 'favorite':
                            if account['base_url'] == post['base_url']:
                                api = self.get_api(account)
                                api.CreateFavorite(int(post['tweet_id']))
                                logging.debug('Favorited %s' % (post['tweet_id'
                                        ], ))
                        elif post['action'] == 'follow':
                            if account['base_url'] == post['base_url']:
                                api = self.get_api(account)
                                api.CreateFriendship(int(post['tweet_id']))
                                logging.debug('Follow %s' % (post['tweet_id'],
                                        ))
                        elif post['action'] == 'unfollow':
                            if account['base_url'] == post['base_url']:
                                api = self.get_api(account)
                                api.DestroyFriendship(int(post['tweet_id']))
                                logging.debug('Follow %s' % (post['tweet_id'],
                                        ))
                        elif post['action'] == 'twitpic':
                            if account['base_url'] \
                                == SUPPORTED_ACCOUNTS[0]['base_url']:
                                api = self.get_api(account)
                                import twitpic
                                twitpic_client = \
                                    twitpic.TwitPicOAuthClient(consumer_key=api._username,
                                        consumer_secret=api._password,
                                        access_token=api._oauth_token.to_string(),
                                        service_key='f9b7357e0dc5473df5f141145e4dceb0'
                                        )
                                params = {}
                                params['media'] = 'file://' + post['base_url']
                                params['message'] = unicode(post['text'])
                                response = twitpic_client.create('upload',
                                        params)
                                if 'url' in response:
                                    self.post_tweet(
                                        post['serialize'],
                                        post['shorten_url'],
                                        unicode(response['url']) + u' : '
                                            + post['text'],
                                        post['latitude'],
                                        post['longitude'],
                                        '',
                                        'tweet',
                                        '',
                                        )
                                else:

                                    raise StandardError('No twitpic url')
                        else:

                            logging.error('Unknow action : %s' % post['action'])

                    os.remove(item)
            except twitter.TwitterError, err:

                if err.message == 'Status is a duplicate.':
                    logging.error('Do_posts (remove): %s' % (err.message, ))
                    os.remove(item)
                elif 'ID' in err.message:
                    logging.error('Do_posts (remove): %s' % (err.message, ))
                    os.remove(item)
                else:
                    logging.error('Do_posts : %s' % (err.message, ))
                if settings.contains('ShowInfos'):
                    if settings.value('ShowInfos') == '2':
                        self.dbus_handler.info('Khweeteur: Error occured while posting: '
                                 + err.message)
            except StandardError, err:
                logging.error('Do_posts : %s' % (str(err), ))
                if settings.contains('ShowInfos'):
                    if settings.value('ShowInfos') == '2':
                        self.dbus_handler.info('Khweeteur: Error occured while posting: '
                                 + str(err))
                import traceback
                (exc_type, exc_value, exc_traceback) = sys.exc_info()
                logging.error('%s' % repr(traceback.format_exception(exc_type,
                              exc_value, exc_traceback)))
            except Exception, err:

                # Emitting the error will block the other tweet post
                # raise #can t post, we will keep the file to do it later

                logging.error('Do_posts : %s' % str(err))
                if settings.contains('ShowInfos'):
                    if settings.value('ShowInfos') == '2':
                        self.dbus_handler.info('Khweeteur: Error occured while posting: '
                                 + str(err))
            except:
                logging.error('Do_posts : Unknown error')

    @Slot()
    def update(self):
        try:
            self.do_posts()
            self.retrieve()
        except Exception:
            import traceback
            (exc_type, exc_value, exc_traceback) = sys.exc_info()
            logging.error('%s' % repr(traceback.format_exception(exc_type,
                          exc_value, exc_traceback)))

    def retrieve(self, options=None):
        logging.debug('Start update')
        settings = settings_db()

        showInfos = False
        if settings.contains('ShowInfos'):
            if settings.value('ShowInfos') == '2':
                showInfos = True

        useGPS = False
        if settings.contains('useGPS'):
            if settings.value('useGPS') == '2':
                useGPS = True

        try:
            # Cleaning old thread reference for keep for gc
            logging.debug('Number of thread not gc : %s' % str(len(self.threads)))

            if len(self.threads)>0:
                return            
#            for thread in self.threads:
#                if not thread.isAlive():
#                    self.threads.remove(thread)
#                    logging.debug('Removed a thread')

            # Remove old tweets in cache according to history prefs

            try:
                keep = int(settings.value('tweetHistory'))
            except:
                keep = 60

            for (root, folders, files) in os.walk(self.cache_path):
                for folder in folders:
                    statuses = []
                    uids = glob.glob(os.path.join(root, folder, '*'))
                    for uid in uids:
                        uid = os.path.basename(uid)
                        try:
                            pkl_file = open(os.path.join(root, folder, uid),
                                    'rb')
                            status = pickle.load(pkl_file)
                            pkl_file.close()
                            statuses.append(status)
                        except StandardError, err:
                            logging.debug('Error in cache cleaning: %s,%s'
                                    % (err, os.path.join(root, uid)))
                    statuses.sort(key=lambda status: \
                                  status.created_at_in_seconds, reverse=True)
                    for status in statuses[keep:]:
                        try:
                            os.remove(os.path.join(root, folder,
                                      str(status.id)))
                        except StandardError, err:
                            logging.debug('Cannot remove : %s : %s'
                                    % (str(status.id), str(err)))

            nb_searches = settings.beginReadArray('searches')
            searches = []
            for index in range(nb_searches):
                settings.setArrayIndex(index)
                searches.append(settings.value('terms'))
            settings.endArray()

            nb_lists = settings.beginReadArray('lists')
            lists = []
            for index in range(nb_lists):
                settings.setArrayIndex(index)
                lists.append((settings.value('id'), settings.value('user')))
            settings.endArray()

            nb_accounts = settings.beginReadArray('accounts')
            logging.info('Found %s account' % (str(nb_accounts), ))
            for index in range(nb_accounts):
                settings.setArrayIndex(index)
                access_token = settings.value('access_token')
                if not access_token in self.apis:                    
                    self.apis[access_token] = self.get_api(dict((key,
                            settings.value(key)) for key in settings.allKeys()))
                    self.me_users[access_token] = None

                if not self.me_users[access_token]:
                    try:
                        self.me_users[access_token] = \
                            self.apis[access_token].VerifyCredentials().id
                    except Exception, err:
                        self.me_users[access_token] = None
                        logging.error('VerifyCredential2 : %s' % str(err))
                        self.dbus_handler.refresh_ended()
                        logging.debug('Finished loop')
                        if showInfos:
                            self.dbus_handler.info(str(err))

                api = self.apis[access_token]
                me_user_id = self.me_users[access_token]

                # If have user:

                if self.me_users[access_token]:

                    # Worker
                    try:
                        self.threads.append(KhweeteurRefreshWorker(api,
                                'HomeTimeline', me_user_id))
                        self.threads[-1].error.connect(self.dbus_handler.info)                        
                        self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                    except Exception, err:
                        logging.error('Timeline : %s' % str(err))

                    try:
                        self.threads.append(KhweeteurRefreshWorker(api,
                                'Mentions', me_user_id))
                        self.threads[-1].error.connect(self.dbus_handler.info)                        
                        self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                    except Exception, err:
                        logging.error('Mentions : %s' % str(err))

                    try:
                        self.threads.append(KhweeteurRefreshWorker(api, 'DMs',
                                 me_user_id))
                        self.threads[-1].error.connect(self.dbus_handler.info)                        
                        self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                    except Exception, err:
                        logging.error('DMs : %s' % str(err))

                    # Start searches thread
                    for terms in searches:
                        try:
                            self.threads.append(KhweeteurRefreshWorker(api,
                                    'Search:' + terms,
                                    me_user_id))
                            self.threads[-1].error.connect(self.dbus_handler.info)                        
                            self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets)                                     
                        except Exception, err:
                            logging.error('Search %s: %s' % (terms, str(err)))

                    # Start retrieving the list
                    try:
                        self.threads.append(KhweeteurRefreshWorker(api,
                                'RetrieveLists', me_user_id))
                        self.threads[-1].error.connect(self.dbus_handler.info)                        
                        self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                    except Exception, err:
                        logging.error('Retrieving List error %s' % (str(err), ))

                    # Near retrieving
                    if useGPS:
                        if not self.geoloc_source:
                            self.geolocStart()
                        if self.geoloc_coordinates:
                            try:
                                self.threads.append(KhweeteurRefreshWorker(api,
                                        'Near:%s:%s' % \
                                           (str(self.geoloc_coordinates[0]),
                                            str(self.geoloc_coordinates[1])),
                                        me_user_id))
                                self.threads[-1].error.connect(self.dbus_handler.info)                        
                                self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                            except Exception, err:
                                logging.error('Near: %s' % (str(err)))


                    # Start lists thread
                    for (list_id, user) in lists:
                        try:
                            self.threads.append(KhweeteurRefreshWorker(api,
                                    'List:' + user + ':' + list_id,
                                    me_user_id))
                            self.threads[-1].error.connect(self.dbus_handler.info)                        
                            self.threads[-1].new_tweets.connect(self.dbus_handler.new_tweets) 
                        except Exception, err:
                            logging.error('List %s: %s' % (list_id, str(err)))

                    # Start the thread
                    try:
                        for (idx, thread) in enumerate(self.threads):
                            logging.debug('Try to run Thread : %s'
                                    % str(thread))
                            try:
                                self.threads[idx].finished.connect(self.athread_end)
                                self.threads[idx].terminated.connect(self.athread_end)
                                self.threads[idx].start()
                                
                            except RuntimeError, err:
                                logging.debug('Attempt to start a thread already running : %s'
                                         % (str(err), ))
                    except Exception, err:
                        logging.error('Running Thread error: %s' % err)

            settings.endArray()

        except Exception, err:
            logging.exception(str(err))

    @Slot()
    def kill_thread(self):
        for thread in self.threads:
            if not thread.isFinished():
                thread.terminate()             
    @Slot()
    def athread_end(self):
        try:
            self.threads.remove(self.sender())
        except ValueError:
            pass
        if all([thread.isFinished() for thread in self.threads]):            
            self.dbus_handler.refresh_ended()
            logging.debug('Finished loop')
        

if __name__ == '__main__':
    install_excepthook(__version__)
    if os.path.exists('/var/run/khweeteurd'):
        daemon = KhweeteurDaemon('/var/run/khweeteurd/khweeteurd.pid')
    else:
        daemon = KhweeteurDaemon('/tmp/khweeteurd.pid')
    if len(sys.argv) == 2:
        if 'startfromprefs' == sys.argv[1]:
            daemon.startfromprefs()
        elif 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'debug' == sys.argv[1]:
            daemon.debug()
        else:
            logging.error('Unknown command')
            print 'Unknown command'
            sys.exit(2)
        sys.exit(0)
    else:
        print 'usage: %s start|stop|restart|startfromprefs|debug' % sys.argv[0]
        sys.exit(2)
