#!/usr/bin/env python
# (c) 2005 Gautier Portet

import sys
import os
assert sys.version >= '2', "Install Python 2.0 or greater"
from distutils.core import setup, Extension

PACKAGE="gxiso"
VERSION=1.0
ALL_LINGUAS=["fr"]

#hack hack HACK !!!
#maybe I will just use autoconf...

def translation_files():
	list = []
	for lang in ALL_LINGUAS:
		list.append(("share/locale/%s/LC_MESSAGES"%lang ,["po/tmp/%s/%s.mo"%(lang,PACKAGE)]  ))
	return list

def update_translations():

	# update main pot file
	potfile = 'po/POTFILES.in'
	
	if not os.path.exists(potfile):
		sys.exit("No such file: '%s'" % potfile)
	
	f = open(potfile)
	files = ""
	
	for line in f:
		# ignore comments and newline
		if line.startswith('#') or line.startswith('\n'):
			continue
		else: 
			files += " "+line.strip()
	f.close()
	
	os.system("xgettext -o po/%s.pot %s" % ( PACKAGE,files) )

	# update langages files
	for lang in ALL_LINGUAS:
		os.system("msgmerge -o po/%s.po po/%s.po po/%s.pot" % (lang, lang, PACKAGE) )
		os.system("msgfmt -o po/%s.mo po/%s.po" % (lang,lang))
		try:
			os.mkdir("po/tmp/%s"%lang)
			os.symlink("../../%s.mo"%lang,"po/tmp/%s/%s.mo"%(lang, PACKAGE))
		except:
			pass

try:
	os.mkdir("po/tmp")
except:
	pass

update_translations()

data = translation_files()
data.append(('share/gxiso', ['src/gxiso.glade','src/gxiso.png']))


setup(
	name = "gxiso",
	version = VERSION,
	description = "A Xbox iso extractor and uploader",
	author = "Gautier Portet",
	author_email = "<kassoulet@gmail.com>",
	url = "http://gxiso.berlios.de",
	license = "GPL",
	data_files = data,
	packages = ["gxiso"],
	package_dir = {"gxiso" : "src"},
	scripts = ["src/gxiso.py"]
)
