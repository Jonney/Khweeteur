#!/usr/bin/python
# -*- coding: utf-8 -*-

#Khweeteur Setup File

from distutils.core import setup

setup(name='Khweeteur',
      version='0.0.1',
      license='GNU GPLv3',
      description='A simple twitter client designed for Maemo and Meego devices, with an unified view',
      author='Benoît HERVIER',
      author_email='khertan@khertan.net',
      url='http://www.khertan.net/khweeteur',
      packages= ['khweeteur',],
      package_data = {'khweeteur': ['icons/*.png']},
      data_files=[('/usr/share/dbus-1/services', ['khweeteur.service']),
                  ('/usr/share/applications/hildon/', ['khweeteur.desktop']),
                  ('/usr/share/pixmaps', ['khweeteur.png'])],
      scripts=['khweeteur_launch.py'],

     )

