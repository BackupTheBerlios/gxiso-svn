#!/usr/bin/env python

import sys
assert sys.version >= '2', "Install Python 2.0 or greater"
from distutils.core import setup, Extension

# not tested, DO NOT USE!

__setup(
	name = "gXiso",
	version = 0.9,
	description = "A Xbox iso extractor and uploader",
	author = "Gautier Portet",
	author_email = "<kassoulet@gmail.com>",
	url = "http://gxiso.berlios.de",
	license = "GPL",
	data_files = [
		('share/pixmaps', ['src/gxiso.png']),
		('share/gxiso', ['src/gxiso.glade'])],
	packages = ["gxiso"],
	package_dir = {'gxiso' : 'src'},
	scripts = ["src/gxiso.py"],
)
