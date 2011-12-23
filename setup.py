#!/usr/bin/python
# -*- coding: utf-8 -*-

#Khweeteur Setup File

import sys
reload(sys).setdefaultencoding("UTF-8")

try:
    from sdist_maemo import sdist_maemo as _sdist_maemo
except ImportError:
    _sdist_maemo = None
    print 'sdist_maemo command not available'

from distutils.core import setup
import khweeteur.qwidget_gui

#Remove pyc and pyo file
import glob,os
for fpath in glob.glob('*/*.py[c|o]'):
    os.remove(fpath)

changes = '* Bug fixes for #976, #967, Replying to a tweet with only one account, #974. Improve the display of new tweets, and add XMasTheme. And always some code cleaning.'

setup(name='khweeteur',
      version=khweeteur.qwidget_gui.__version__,
      license='GNU GPLv3',
      description="A twitter client for Maemo and MeeGo.",
      long_description="Khweeteur is a small twitter client for Maemo and MeeGo. It showing DMs, mentions, searchs, lists, and the follower timeline in one window. Maemo's notification system is supported and can notify for dmsse or mentions even when the ui is not launched, as is auto-update and themeing.",
      author='Benoît HERVIER',
      author_email='khertan@khertan.net',
      maintainer=u'Benoit HERVIER',
      maintainer_email='khertan@khertan.net',
      requires=['imaging','simplejson','conic','PySide','PySide.QtMobility', \
                'httplib2'],
      url='http://www.khertan.net/khweeteur',
      packages= ['khweeteur','khweeteur.oauth', 'khweeteur.oauth2', 'khweeteur.pydaemon', 'khweeteur.pydaemon.version'],
      package_data = {'khweeteur': ['icons/*.png']},
      data_files=[('/usr/share/dbus-1/services', ['khweeteur.service', 'khweeteur-daemon.service']),
                  ('/usr/share/applications/hildon/', ['khweeteur.desktop']),
                  ('/usr/share/pixmaps', ['khweeteur.png','khweeteur_64.png','khweeteur_32.png']),
                  ('/usr/share/icons/hicolor/128x128/apps', ['khweeteur.png']),
                  ('/usr/share/icons/hicolor/64x64/apps', ['icons/hicolor/64x64/apps/khweeteur.png']),
                  ('/usr/share/icons/hicolor/32x32/apps', ['icons/hicolor/32x32/apps/khweeteur.png']),
                  ('/etc/event.d', ['khweeteurd']),],
      scripts=['scripts/khweeteur', 'scripts/khweeteur-daemon'],
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Programming Language :: Python",
        "Operating System :: POSIX :: Linux",
        "Operating System :: POSIX :: Other",
        "Operating System :: Other OS",
        "Intended Audience :: End Users/Desktop",],
      cmdclass={'sdist_maemo': _sdist_maemo},
      options = { 'sdist_maemo':{
      'debian_package':'khweeteur',
      'buildversion':'1',
      'depends':'python2.5, libshiboken1.0 (>=1.0.3-1maemo1), pyside-mobility,libpyside1.0 (>=1.0.3-1maemo2), python-pyside.qtmaemo5 (>=1.0.3-1maemo2), python-pyside.qtwebkit (>=1.0.3-1maemo2), python-pyside.qtcore (>=1.0.3-1maemo2), python-pyside.qtgui (>=1.0.3-1maemo2), python-simplejson, python-conic, python-imaging, python-dbus, python-httplib2, pywoodchuck, murmeltier',
      'conflicts':'khweeteur-experimental',
      'XSBC_Bugtracker':'http://khertan.net/khweeteur:bugs',
      'XB_Maemo_Display_Name':'Khweeteur',
      'XB_Maemo_Icon_26':'khweeteur.png',
      'XB_Maemo_Upgrade_Description':'%s' % changes,
      'section':'user/network',
      'changelog':changes,
      'architecture':'any',
      'postinst':"""#!/bin/sh
chmod +x /usr/bin/khweeteur
python -m compileall /usr/lib/python2.5/site-packages/khweeteur
NOTIFICATIONS_CONF="/etc/hildon-desktop/notification-groups.conf"
NOTIFICATIONS_KEY="khweeteur-new-tweets"
if ! grep -q "$NOTIFICATIONS_KEY" "$NOTIFICATIONS_CONF"; then
echo -n "Updating $NOTIFICATIONS_CONF..."
cat >>$NOTIFICATIONS_CONF << EOF
### BEGIN Added by Khweeteur postinst ###
[khweeteur-new-tweets]
Destination=Khweeteur
Icon=khweeteur
Title-Text-Empty=Khweeteur
Secondary-Text=New tweets available
Text-Domain=khweeteur
LED-Pattern=PatternCommonNotification
### END Added by khweeteur postinst ###
EOF
    echo "done."
fi
# Don't die gratuitously: the daemon may not be running.
su user -c "run-standalone.sh /usr/bin/python /usr/lib/python2.5/site-packages/khweeteur/daemon.py stop" || true
su user -c "run-standalone.sh /usr/bin/python /usr/lib/python2.5/site-packages/khweeteur/daemon.py startfromprefs"
""",
      'prere':"""#!/bin/sh
rm -rf /usr/lib/python2.5/site-packages/khweeteur/*.pyc""",
      'copyright':'gpl'},
      'bdist_rpm':{
      'requires':'python, python-setuptools, python-qtmobility, python-pyside.qtcore, python-pyside.qtgui, python-pyside.qtmaemo5, python-pyside.qtwebkit, pyside-mobility-bearer, python-simplejson, python-conic, python-imaging',
      'conflicts':'khweeteur',
      'icon':'khweeteur.png',
      'group':'Network',}}
     )
