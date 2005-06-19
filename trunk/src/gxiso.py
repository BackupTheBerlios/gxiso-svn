#!/usr/bin/env python

# gXiso - GTK2 Xbox Xiso eXtractor
# Copyright ( C) 2005 Gautier Portet < kassoulet gmail com >

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import sys
import time
import re
import struct
import thread
import ftplib
import socket
import pygtk

if sys.platform != 'win32':
	pygtk.require('2.0')
else:
	from _winreg import * 		import msvcrt		def win32_popen(command):		f = saved_popen(command)
		msvcrt.setmode(f.fileno(),os.O_BINARY)		return f			saved_popen = os.popen	os.popen = win32_popen

import gtk
import gtk.glade
import gettext
import pango
import atk

import bz2
import gzip


BUFFER_SIZE=1024*16

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

FILE_DIR = 0x10

def gtk_iteration():
	# allow GTK to process events outside mainloop
	while gtk.events_pending():
		gtk.main_iteration(False)

def read_unpack(file, format):
	# read and unpack a structure as in struct.unpack
	buffer = file.read(struct.calcsize(format))
	return struct.unpack(format,buffer)

class ExtractError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return str(self.message)

def show_error(message):
	# display a message dialog with an error message
	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
		gtk.BUTTONS_OK, message)
	dialog.set_markup(message)
	dialog.run()
	dialog.hide()

def log(message):
	# display a log message on stdout
	print message


# use FileChooser or FileSelection ?
try:
	dir(gtk.FileChooserDialog)

	def CreateFileChooser(title="", patterns=()):

		dialog = gtk.FileChooserDialog(title, None,
			action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

		if patterns:
			filter = gtk.FileFilter()
			for pattern in patterns:
				filter.add_pattern(pattern)
			dialog.set_filter(filter)
		dialog.set_local_only(True)
		return dialog


	def CreateFolderChooser(title=""):
		dialog = gtk.FileChooserDialog(title, None,
			action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER, buttons=(gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		return dialog

except AttributeError:
	log("using deprecated FileSelection Dialog")

	def CreateFileChooser(title="", patterns=()):
		dialog = gtk.FileSelection(title)
		return dialog

	CreateFolderChooser = CreateFileChooser


total_size=0



class ReaderError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return str(self.message)

class FileReader:
	patterns = (".iso",)
	archive = False
	def __init__(self, filename):
		self.size = os.path.getsize(filename)
		try:
			self.file = open(filename,"rb")
		except IOError:
			raise ReaderError(_("Cannot read file:'%s'") % filename)
		self.position = 0
		self.skipped = 0

	def read(self, size):
		self.position += size
		return self.file.read(size)
		
	def skip(self, offset):
		#print "skip:", offset 
		self.position += offset
		self.file.seek(offset, SEEK_CUR)
		self.skipped += offset
		
	def seek(self, position):
		self.skip(position-self.position)
		self.position = position
	
	def close(self):
		self.file.close()
		print "skipped %d bytes." % self.skipped


class GenericArchiveReader:
	archive = True
	
	def __init__(self, filename):
		self.position = 0
		self.skipped = 0
		
		try:
			f = open(filename, "r")
			f.close()
		except IOError:
			raise ReaderError(_("Cannot open archive: '%s'") % filename)

		self.create_stream(filename)

	def read(self, size):
		self.position += size
		return self.stream.read(size)
		
	def skip(self, offset):
		if offset<0:
			sys.exit()
		while offset:
			n = offset
			if (n>BUFFER_SIZE):
				n = BUFFER_SIZE
			offset -= n
			self.read(n)
			
		self.skipped += offset
		
	def seek(self, position):
		self.skip(position-self.position)
		self.position = position
	
	def close(self):
		self.stream.close()



class RarReader (GenericArchiveReader):
	patterns = (".rar", ".000", ".001", ".r00", ".r01")
	
	def create_stream(self, filename):
		# detecting unrar
		unrar_list=("rar","unrar", "c:/Progra~1/WinRAR/Rar.exe")
		unrar = None
		for i in unrar_list:
			if os.popen(i).read():
				unrar = i
		if not unrar:
			raise ReaderError(_("Cannot find a RAR extractor"))
		
		list_stream = os.popen('%s v "%s"' % (unrar, filename) )
		list = list_stream.read()
		results = re.findall(r" (.+)\s+(\d+) (\d+)",list)

		iso = [file for file in results if ".iso" in file[0].lower()]
		# TODO: check for no iso in rar!
		if not iso:
			raise ReaderError(_("Cannot find a .iso in RAR:\n%s") % filename)
		
		iso = iso[0]
		iso_name = iso[0]
		self.size = int(iso[1])
		self.stream = os.popen( '%s p -inul "%s" "%s"' % (unrar, filename, iso_name))
		

class GZipReader (GenericArchiveReader):
	patterns = (".gz",)
	
	def create_stream(self, filename):
		self.stream = gzip.GzipFile(filename, "r", 0)
		self.size = 0


class BZ2Reader (GenericArchiveReader):
	patterns = (".bz2",)
	
	def create_stream(self, filename):
		self.stream = bz2.BZ2File(filename, "r", 0)
		self.size= 0


readers = (
	FileReader,
	RarReader,
	GZipReader,
	BZ2Reader,
)

def create_reader(filename):
	root, ext = os.path.splitext(filename)
	if not ext:
		return None
	
	for reader in readers:
		for pattern in reader.patterns:
			if ext.lower() == pattern:
				return reader(filename)
	raise IOError
	return None #FileReader(filename)

def is_archive(filename):
	root, ext = os.path.splitext(filename)
	if not ext:
		return False
	
	for reader in readers:
		for pattern in reader.patterns:
			if ext.lower() == pattern:
				if reader.archive:
					return True
	return False

def format_speed(speed):
	"""
	convert a speed in bytes per second in 
	"""
	speed = speed/(1024.0*1024.0)
	return "%.3f MiB/s" % speed


"""
extractors = (
	BZip2Extractor(),
	GZipExtractor(),
)

def extractor_factory(filename):
	for extractor in extractors:
		if extractor.isValid(filename):
			return extractor
	return None
"""
class NullWriter:
	# do nothing writer
	def init(self):
		pass
	def open(self, filename):
		pass
	def write(self, buffer):
		pass
	def close(self):
		pass
	def mkdir(self, name):
		return True
	def chdir(self, name):
		return True
	def quit(self):
		pass

class FileWriter:
	# write to a file
	def __init__(self, base_folder):
		self.base_folder = base_folder
	def init(self):
		try:
			os.makedirs(self.base_folder)
		except OSError:
			# folders maybe already here ?
			pass
		# TODO: we must check for an error !
		self.chdir(self.base_folder)
		#print self.base_folder ##

	def open(self, filename):
		self.file = open(filename,"wb")
	def write(self, buffer):
		self.file.write(buffer)
	def close(self):
		self.file.close()
	def mkdir(self, name):
		try:
			os.mkdir(name)
		except OSError:
			return False
		return True
	def chdir(self, name):
		try:
			os.chdir(name)
		except OSError:
			return False
		return True
	def rename(self, old, new):
		try: 
			os.rename(old, new)
			return True
		except OSError:
			return False
	def quit(self):
		pass

class FTPWriter:
	def __init__(self, ip, login, password, base_folder):
		self.ip = ip
		self.login = login
		self.password = password
		self.base_folder = base_folder
		self.buffer = None

	def makedirs(self, path):
		# create all folders in path
		path.replace("\\","/")
		dirs = path.split("/")
		for folder in dirs:
			if folder != "":
				if not self.chdir(folder):
					if not self.mkdir(folder):
						raise ExtractError(_("<b>Cannot create folder on xbox:</b>\n%s"%path ))
					self.chdir(folder)

	def init(self):
		# connect to ftp
		log("connecting to %s@%s" % (self.login,self.ip))
		try:
			self.session = ftplib.FTP(self.ip,self.login,self.password)
			self.makedirs(self.base_folder)
			self.session.set_pasv(False)
		except ftplib.all_errors, details:
			if details.__class__ == socket.error:
				details = details[1]

			raise ExtractError(_("<b>Cannot connect to xbox:</b>\n"+str(details)))

		try:
			log("Disabling FREEROOTSPACE on Avalaunch")
			self.session.sendcmd("SITE FREEROOTSPACEDISABLE")
		except ftplib.all_errors, details:
			log("  Avalaunch is not here.")

		# we must lock the buffer since its shared between 2 threads
		self.lock = thread.allocate_lock()

	def quit(self):
		# end ftp session
		try:
			self.session.quit()
		except:
			pass

	def upload(self,filename):
		# upload a file
		try:
			self.session.storbinary("STOR %s" % filename, self)
		except ftplib.error_reply, details:
			log( "warning: STOR '%s' = %s" % (filename,str(details)) )
		except ftplib.all_errors, details:
			self.error = _("<b>Cannot write to xbox:</b>\n"+str(details))
		self.lock.acquire()
		self.buffer=None
		self.lock.release()

	def open(self, filename):
		# new file
		self.buffer = ""
		self.closing = False
		self.error = None

		thread.start_new_thread(self.upload,(filename,))
		self.filename = filename

	def write(self, buffer):
		# fill buffer with data from file
		try:
			while len(self.buffer) > 0:
				# wait buffer read
				time.sleep(0.001)
		except TypeError:
			# an error ocurred
			raise ExtractError(self.error)

		# append to buffer
		self.lock.acquire()
		self.buffer += buffer
		self.lock.release()

	def close(self):
		# end of the file
		self.closing = True

		while True:
			# wait end of buffer upload
			wait = True
			self.lock.acquire()
			if self.buffer == None:
				wait = False
			self.lock.release()
			if not wait:
				break
			time.sleep(0.001)


	def mkdir(self, name):
		try:
			self.session.mkd(name)
		except ftplib.error_reply:
			pass
		except ftplib.all_errors:
			return False
		return True
	def chdir(self, name):
		try:
			self.session.cwd(name)
		except ftplib.error_reply:
			pass
		except ftplib.all_errors:
			return False
		return True

	def rename(self, old, new):
		try:
			self.session.rename(old, new)
			return True
		except ftplib.error_reply:
			pass
		except ftplib.error_perm:
			return False
		except ftplib.error_perm:
			return False
		

	def read(self, size):
		# called by ftp storbinary
		while True:
			# wait for buffer to be filled
			self.lock.acquire()
			l = len(self.buffer)
			self.lock.release()
			if l > 0:
				break
			time.sleep(0.001)
			if self.closing:
				return ""

		self.lock.acquire()
		l = len(self.buffer)
		buffer = self.buffer[:size]
		self.buffer = self.buffer[size:]
		self.lock.release()
		return buffer

		

class FileAndFTPWriter:
	def __init__(self, local_folder, ip, login, password, ftp_folder):
		self.file = FileWriter(local_folder)
		self.ftp = FTPWriter(ip,login,password,ftp_folder)
	def init(self):
		self.file.init()
		self.ftp.init()
	def open(self, filename):
		self.file.open(filename)
		self.ftp.open(filename)
	def write(self, buffer):
		self.file.write(buffer)
		self.ftp.write(buffer)
	def close(self):
		self.file.close()
		self.ftp.close()
	def mkdir(self, name):
		self.file.mkdir(name)
		self.ftp.mkdir(name)
	def chdir(self, name):
		self.file.chdir(name)
		self.ftp.chdir(name)
	def rename(self, old, new):
		l = self.file.rename(old, new)
		f = self.ftp.rename(old, new)
		if l and f:
			return True
		return False
	def quit(self):
		self.file.quit()
		self.ftp.quit()


dir_str = ""
file_str= ""


def ftp_delete_folder__(session, folder):
	session.cwd(folder)
	list = []
	session.retrlines('LIST -a', list.append)


	for entry in list:
		#print entry
		is_folder = False
		
		if entry[0] == "d":
			is_folder = True
		
		entry = entry.split(None, 8)
		filename = entry[8]
		if is_folder:
			ftp_delete_folder__(session, filename)
			session.cwd("..")
			session.rmd(filename)
		else:
			session.delete(filename)
	
def ftp_delete_folder(session, base_folder, folder_to_delete):
	try:
		ftp_delete_folder__(session, "/".join( (base_folder,folder_to_delete) ))
		session.cwd(base_folder)
		session.rmd(folder_to_delete)	
	except ftplib.error_perm:
		print "error while deleting:", "/".join( (base_folder,folder_to_delete) )

class XisoExtractor:

	def __init__(self, writer):
		self.writer = writer
		self.xbe_name = None
		self.size=0
		self.files=0
		self.write_position=0
		self.base_folder = ""
		self.current_file = ""
		self.paused = False
		self.canceled = False
		self.error = None
		self.active=True

	def parse_xbe(self):
		readsize = 0x190 + 80
		buffer = self.iso.read(readsize)
		name = buffer[-80:]

		self.xbe_name = ""

		if not name:
			name = ""
				
		# TODO: better solution for wide chars
		for i in range(len(name)):
			if name[i] != "\x00":
				self.xbe_name += name[i]
		print "detected xbename:", self.xbe_name	

		self.writer.write(buffer);
		self.write_position += readsize
		
	def write_file(self,filename,size,sector):
		# actually write or upload the file
		self.current_file = filename

		self.iso.seek(sector*2048)
		self.writer.open(filename)

		buffer = "-"
		try:
			if filename.lower() == "default.xbe":
				# search xbe real name
				self.parse_xbe()
				size -= 0x190 + 80
				
			while buffer:
				readsize = min(size,BUFFER_SIZE)
				buffer = self.iso.read(readsize)
				self.writer.write(buffer);
				size -= readsize
				self.write_position += readsize
				if size<0:
					break
				if self.canceled:
					return
				while self.paused:
					time.sleep(0.1)
		finally:
			self.writer.close()

	def handle_folders(self, new_folders):
		
		current_folders = self.current_folders
		
		delta = len(current_folders) - len(new_folders)	
		if delta > 0:
			for i in range(delta):
				new_folders.append("")
		if delta < 0:
			for i in range(-delta):
				current_folders.append("")

		##print  "/".join(current_folders), "/".join(new_folders)

		current = current_folders[:]
		new = new_folders[:]

		for i in range(len(new)):
			n = new[0]
			c = current[0]
			if n == c:
				new.pop(0)
				current.pop(0)
			else:
				break

		for i in current:
			if i:
				self.writer.chdir("..")
		
		for i in new:
			if i:
				self.writer.mkdir(i)
				if not self.writer.chdir(i):
					raise ExtractError(_("<b>Cannot change to directory:</b>%s") % i)
		self.current_folders = new_folders

	def browse_file(self, sector, filename, size, folders):
	
		self.handle_folders(folders)
		#print "%11d file:  %40s (%10d)" % (sector*2048, filename, size)
		self.files += 1
		self.write_file(filename, size, sector)

	def browse_entry(self, sector, offset, folders):
		pos = sector*2048+offset
		
		# jump to sector
		self.iso.seek(pos)

		# read file header
		ltable, rtable, newsector, filesize, attributes, filename_size \
		= read_unpack(self.iso, "<HHLLBB")
		
		# read file name
		filename = self.iso.read(filename_size)

		#print "%11d entry: %40s %s" % (pos, filename, "/".join(folders))
		
		if (attributes & FILE_DIR > 0) and (filename_size>0):
			nfolders = folders[:]
			nfolders.append(filename)
			#print "/", filename
			self.sector_list.append( (newsector*2048, newsector, 0, "entry", filename, 0, nfolders) )
		else:
			# write file
			if filename:
				self.size  = self.size + filesize
				self.total_files += 1
				self.sector_list.append( (newsector*2048, newsector, 0, "file", filename, filesize, folders) )
			else:
				log("warning: file without filename (offset:%d ,size:%d)" % \
						(newsector, filesize) )

		if rtable > 0:
			self.sector_list.append( ( sector*2048+rtable ,sector, rtable*4, "entry", "", 0, folders) )
		if ltable > 0:
			self.sector_list.append( ( sector*2048+ltable ,sector, ltable*4, "entry", "", 0, folders) )


	def browse_sector(self):
		while self.sector_list:
			# maintain list sorted by sector 
			self.sector_list.sort()
		
			pos, sector, offset, type, filename, size, folders = \
				self.sector_list.pop(0)
			if type == "entry":
				self.browse_entry(sector, offset, folders)
			if type == "file":
				self.browse_file(sector, filename, size, folders)
		
			if self.canceled:
				return
			

	def browse_start(self, sector):

		self.sector_list = []
		self.current_folders = []
		self.sector_list.append( (sector*2048, sector, 0, "entry", "", 0, []) )
		self.browse_sector()

	def extract(self,iso_name):
		# parse and extract iso

		self.active=True
		saved_folder = os.getcwd()
		self.error = None
		try:
			self.writer.init()
			self.parse_internal(iso_name)
			self.writer.quit()
		except ExtractError, details:
			self.error = details.message
		os.chdir(saved_folder)
		self.active=False

	def parse_UNUSED(self,iso_name):
		# only parse iso
		if is_archive(iso_name):
			self.size = 2
			self.files = 1
			return  
	
		self.size=0
		self.files=0
		#return ##
	
		self.write_file = self.write_file_parse
		return self.parse_internal(iso_name)

	def parse_internal(self,iso_name):
		# internal parser

		self.files = 0
		self.size  = 0
		self.write_position=0
		self.total_files = 0

		log("opening xiso: "+iso_name);

		# make sure file is really readable in whole
		try:
			test = file(iso_name, "rb")
		except IOError:
			raise ExtractError( _("<b>Cannot read iso</b>") )
		
		try:
			test.seek(0,SEEK_END)
		except IOError:
			raise ExtractError( _("<b>Cannot read whole iso (too big ?)</b>") )
		test.close()

		try:
			self.iso = create_reader(iso_name)
		except ReaderError, error:
			raise ExtractError( _("<b>Cannot open iso:</b>\n%s") % error )

		signature = "\x4d\x49\x43\x52\x4f\x53\x4f\x46\x54\x2a\x58\x42\x4f\x58\x2a\x4d\x45\x44\x49\x41"

		# skip beggining
		self.iso.skip(0x10000)

		# read and verify header
		header = self.iso.read(0x14)
		if header != signature:
			raise ExtractError( _("<b>Not a valid xbox iso image</b>") )

		# read root sector address
		root_sector, = read_unpack(self.iso, "<L")

		# skip root_size + FILETIME + unused
		self.iso.skip(0x7d4)

		# read and verify header
		header = self.iso.read(0x14)
		if header != signature:
			raise ExtractError( _("<b>Not a valid xbox iso image</b>") )

		# and start extracting files
		self.browse_start(root_sector)
		self.iso.close()

		return None

class Window:
	# all windows herits from this class
	def load_glade(self, xml, container):
		self.dialog_xml = gtk.glade.XML(xml, container)

		signals = {}
		for iteration in dir(self):
			# automatically connect to XML GUI
			if iteration[:3] == "on_":
				# events
				signals[iteration] = getattr(self,iteration)
			elif iteration[:3] == "ui_":
				# widgets
				setattr(self,iteration,self.dialog_xml.get_widget(iteration[3:]))

		self.dialog_xml.signal_autoconnect(signals)

	def get_widget(self, name):
		return self.dialog_xml.get_widget(name)

class DialogProgress(Window):
	def __init__(self):
		# widgets we will connect to
		self.ui_label_operation =\
		self.ui_label_detail =\
		self.ui_progressbar =\
		self.ui_dialog_progress =\
			None

		self.load_glade("gxiso.glade", "dialog_progress")

	def start(self):
		self.starttime=time.time()
		self.canceled = False
		self.paused = False
		self.pausetime = 0
		self.current_file = ""
		self.current_speed = 0

	def stop(self):
		self.ui_dialog_progress.hide_all()

	def set_current_operation(self, operation):
		self.ui_label_operation.set_markup("<b>%s</b>" % operation)

	def set_current_file(self, filename):
		self.ui_label_detail.set_markup("<i>%s</i>" % filename)
		#self.current_file = number
		#self.total_files = total

	def set_current_speed(self, speed):
		self.current_speed = speed

	def pulse(self):
		self.ui_progressbar.pulse()

	def set_fraction(self, fraction):
		self.ui_progressbar.set_fraction(fraction)
		now=time.time()
		if fraction<0.01: 
			fraction = 0.01
		remaining = ((now-self.starttime) / fraction-(now-self.starttime))
		minutes = remaining/60.0
		if minutes<1:
			text = _("less than one minute left.")
		elif minutes==1:
			text = _("about one minute left.")
		else :
			text = _("about %d minutes left." % minutes)

		if self.paused:
			text = _("Paused")

		self.ui_progressbar.set_text(_("%.3f MiB/s, %s") %
			(self.current_speed/(1024*1024.0), text))

	def on_button_pause_clicked(self, widget):
		self.paused = not self.paused
		if self.paused:
			# pause
			self.pausetime = time.time()
		else:
			# remove paused time
			self.starttime += time.time()-self.pausetime

	def on_button_cancel_clicked(self, widget):
		self.canceled = True


class DialogMain(Window):

	def __init__(self):

		# default settings
		self.default_settings = {
			"extract": False,
			"upload": True,
			"xbox_ip": "192.168.0.6",
			"xbox_login": "xbox",
			"xbox_password": "xbox",
			"xbox_drive": 2,
			"xbox_folder": "games"
		}
		self.settings = self.default_settings

		# widgets we will connect to
		self.ui_checkbutton_extract =\
		self.ui_checkbutton_upload =\
		self.ui_entry_xbox_folder =\
		self.ui_entry_xbox_address =\
		self.ui_entry_xbox_login =\
		self.ui_entry_xbox_password =\
		self.ui_combobox_xbox_drive =\
		self.ui_entry_xiso =\
		self.ui_entry_folder =\
		self.ui_button_folder_browse =\
		self.ui_vbox_upload =\
		self.ui_label_iso_infos =\
			None

		self.xbe_name = None
		self.load_glade("gxiso.glade", "dialog_main")

	def load_settings(self):
		filename = os.path.expanduser("~/.gxiso")
		try:
			f = open(filename,"r")
		except IOError:
			log("warning: cannot read "+filename)
			return

		try:
			self.settings = eval(f.read(-1))
		except SyntaxError:
			pass

		f.close()
		try:
			self.settings_to_ui()
		except KeyError:
			log("warning: error while applying settings, fallback to defaults.")
			self.settings = self.default_settings
			self.settings_to_ui()

	def save_settings(self):

		self.settings_from_ui()
		filename = os.path.expanduser("~/.gxiso")
		try:
			f = open(filename,"w")
			f.write( repr(self.settings) )
			f.close()
		except IOError:
			log("warning: cannot write "+filename)

	def settings_to_ui(self):
		self.ui_checkbutton_extract.set_active(self.settings["extract"])
		self.ui_checkbutton_upload.set_active(self.settings["upload"])
		self.ui_entry_xbox_address.set_text(self.settings["xbox_ip"])
		self.ui_entry_xbox_login.set_text(self.settings["xbox_login"])
		self.ui_entry_xbox_password.set_text(self.settings["xbox_password"])
		self.ui_entry_xbox_folder.set_text(self.settings["xbox_folder"])
		self.ui_combobox_xbox_drive.set_active(self.settings["xbox_drive"])

	def settings_from_ui(self):
		self.settings["extract"] = self.ui_checkbutton_extract.get_active()
		self.settings["upload"] = self.ui_checkbutton_upload.get_active()
		self.settings["xbox_ip"] = self.ui_entry_xbox_address.get_text()
		self.settings["xbox_login"] = self.ui_entry_xbox_login.get_text()
		self.settings["xbox_password"] = self.ui_entry_xbox_password.get_text()
		self.settings["xbox_folder"] = self.ui_entry_xbox_folder.get_text()
		self.settings["xbox_drive"] = self.ui_combobox_xbox_drive.get_active()

	def apply_ui_changes(self):
		# extract
		if self.ui_checkbutton_extract.get_active():
			self.ui_entry_folder.set_sensitive(True)
			self.ui_button_folder_browse.set_sensitive(True)
		else:
			self.ui_entry_folder.set_sensitive(False)
			self.ui_button_folder_browse.set_sensitive(False)

		# upload
		if self.ui_checkbutton_upload.get_active():
			self.ui_vbox_upload.set_sensitive(True)
		else:
			self.ui_vbox_upload.set_sensitive(False)

	def get_iso_infos(self, filename):
		xiso = XisoExtractor(NullWriter())
		error = xiso.extract(filename)
		if error:
			self.xbe_name = None
			self.ui_label_iso_infos.set_markup(error)
		else:
			self.xbe_name = xiso.xbe_name
			self.ui_label_iso_infos.set_markup(_("Title name: <b>%s</b> (%d MB)") %
			(self.xbe_name, os.path.getsize(filename)/(1024*1024)) )
			if self.ui_entry_folder.get_text() and self.xbe_name != "":
				self.ui_entry_folder.set_text(os.path.join(os.getcwd(),self.xbe_name))

	def xboxify_filename(self, filename):
		filters = (
			".",
			",",
			";",
			":",
		)
		
		print repr(filename)
		
		name = filename[:40]
		for f in filters:
			name = name.replace(f," ")
		return name

	def extract_archive_UNUSED(self, extractor, filename):
		self.extracted_filename = extractor.extract(filename)
		self.extracting = False

	def create_tmp_folder(self, ip, login, password, folder):
		
		writer = FTPWriter(ip, login, password, folder)
		writer.init()
		for i in range(1000):
			name = "gxiso%03d" % i
			if writer.mkdir(name):
				break;
				
		writer.close()
		return name

	def extract_xiso(self):
		self.extracted_filename = None

		# get infos from ui
		drives = ["/c/","/e/","/f/","/g/"]
		filename = self.ui_entry_xiso.get_text()
		local_folder = self.ui_entry_folder.get_text()
		ftp_folder = drives[self.ui_combobox_xbox_drive.get_active()] + \
			self.ui_entry_xbox_folder.get_text()

		if ftp_folder[-1] != "/":
			ftp_folder += "/"

		ftp_ip = self.ui_entry_xbox_address.get_text()
		ftp_login = self.ui_entry_xbox_login.get_text()
		ftp_password = self.ui_entry_xbox_password.get_text()

		extract = self.ui_checkbutton_extract.get_active()
		upload = self.ui_checkbutton_upload.get_active()

		rename = None
		if self.xbe_name:
			ftp_folder += self.xboxify_filename(self.xbe_name)
		else:
			if upload:
				try:
					name = self.create_tmp_folder(ftp_ip,ftp_login,ftp_password,ftp_folder)
				except ExtractError, error:
					show_error(error.message)
					return
				rename = name
				print "creating temp folder:", name
				ftp_base_folder = ftp_folder
				tmp_folder = name
				ftp_folder += name

		# init progress dialog
		progress = DialogProgress()
		progress.set_current_operation(_("Parsing"))
		progress.set_current_file("")
		gtk_iteration()
	
		# select writer plugin
		writer = NullWriter()
		if extract and not upload:
			writer = FileWriter(local_folder)
			operation = _("Extracting")
		if not extract and upload:
			writer = FTPWriter(ftp_ip, ftp_login, ftp_password, ftp_folder)
			operation = _("Uploading")
		if extract and upload:
			writer = FileAndFTPWriter(local_folder, ftp_ip, ftp_login, ftp_password, ftp_folder)
			operation = _("Extracting and Uploading")
		if not extract and not upload:
			# what are we doing here ? :)
			progress.stop()
			return

		# and start the extraction thread
		if upload:
			progress.set_current_operation(_("Connecting to ftp://%s@%s")%
				(ftp_login, ftp_ip) )
		progress.start()
		gtk_iteration()

		xiso = XisoExtractor(writer)
		thread.start_new_thread(xiso.extract, (filename,))

		previous_position = 0
		time_inactive = 0.0
		previous_position = 0
		mean_speed = 0
		delay = 0

		while xiso.active and not xiso.canceled:
			if xiso.write_position == 0:
				# still not writing
				progress.pulse()
			else:
				if operation:
					# display the current mode, once
					progress.set_current_operation(operation)
					operation = None
				# update progress
				progress.set_current_file(xiso.current_file)
								
				if xiso.iso.size:
					fraction = float(xiso.write_position)/float(xiso.iso.size)
					mean_speed = xiso.write_position/(time.time()-progress.starttime)
					if not xiso.paused:
						progress.set_current_speed(mean_speed)
					delay += 0.1
					if delay >= 1.0:
						progress.set_fraction(fraction)
						delay = 0
				else:
					progress.pulse()

				# detect transfer timeout
				if xiso.write_position == previous_position:
					time_inactive += 0.1
				else:
					time_inactive = 0
				if upload and time_inactive > 5.0 and not xiso.paused:
					xiso.error = _("<b>Transfer timeout</b>\nThe xbox is not responding")
					xiso.active = False
				previous_position = xiso.write_position

			# handle events
			xiso.canceled = progress.canceled
			xiso.paused = progress.paused


			# and let our working thread be called
			gtk_iteration()
			time.sleep(0.1)

			
		
		if rename:
			try:
				writer = FTPWriter(ftp_ip, ftp_login, ftp_password, ftp_folder)
				writer.init()
				if xiso.canceled:
					log( "deleting: %s" % (ftp_base_folder+tmp_folder) )
					progress.set_current_operation(_("Deleting temporary files"))
					ftp_delete_folder(writer.session, ftp_base_folder, tmp_folder)
				elif xiso.xbe_name:
					writer.chdir(ftp_base_folder)
					newname = self.xboxify_filename(xiso.xbe_name)
					log( "deleting: %s" % (ftp_base_folder+newname) )
					ftp_delete_folder(writer.session, ftp_base_folder, newname)
					log( "renaming: %s -> %s" % (rename, newname) )
					if not writer.rename(rename, newname):
						show_error( _("Cannot rename <i>%s</i> to <i>%s</i>") \
							% (rename, newname) )
			except ExtractError, error:
				show_error(error.message)

		if xiso.error:
			show_error(xiso.error)
		elif not xiso.canceled:
			log( "done! (in %ds, %.3f MiB/s)" % (time.time()-progress.starttime,xiso.write_position/(time.time()-progress.starttime)/(1024*1024.0)))
		progress.stop()

	def on_button_defaults_clicked(self, widget):
		self.settings = self.default_settings
		self.settings_to_ui()
		self.save_settings()

	def on_button_ok_clicked(self, widget):
		if self.ui_entry_xiso.get_text() == "":
			show_error(_("Please select an iso to read."))
		else:
			self.extract_xiso()


	def on_button_xiso_browse_clicked(self, widget):
		patterns = []
		for p in readers:
			patterns.extend( ["*"+i.lower() for i in p.patterns] )
			patterns.extend( ["*"+i.upper() for i in p.patterns] )
		
		dialog = CreateFileChooser(_("Open Xbox Iso"), patterns)
		dialog.show_all()
		result = dialog.run()
		dialog.hide_all()
		if result == gtk.RESPONSE_OK:
			self.iso_name = dialog.get_filename()
			self.ui_entry_xiso.set_text(self.iso_name)
			###self.get_iso_infos(self.iso_name)
			if (self.xbe_name):
				pass
				#self.ui_entry_folder.set_text(os.path.join(os.getcwd(),self.xbe_name))
				#self.ui_label_xbox_folder.set_markup("<small>%s</small>" % self.xbe_name)
			else:
				name = os.path.basename(self.iso_name)
				name, ext = os.path.splitext(name)
				#self.ui_label_xbox_folder.set_markup("<small>%s</small>" % name)

	def on_button_folder_browse_clicked(self, widget):
		dialog = gtk.FileChooserDialog(_("Select Extract Folder"),None,
			action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER, buttons=(gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

		dialog = CreateFolderChooser(_("Select Extract Folder"))

		if self.xbe_name:
			dialog.set_current_name(self.xbe_name)

		dialog.show_all()
		result = dialog.run()
		dialog.hide_all()
		if result == gtk.RESPONSE_OK:
			self.ui_entry_folder.set_text(dialog.get_filename())

	def on_checkbutton_extract_toggled(self, widget):
		self.settings["extract"] = self.ui_checkbutton_extract.get_active()
		self.apply_ui_changes()

	def on_checkbutton_upload_toggled(self, widget):
		self.settings["upload"] = self.ui_checkbutton_upload.get_active()
		self.apply_ui_changes()

	def on_button_quit_clicked(self, widget):
		self.save_settings()
		gtk.main_quit()

	def on_destroy(self, widget, data=None):
		self.save_settings()
		gtk.main_quit()

	def show(self):
		# main window
		self.load_settings()
		self.apply_ui_changes()

class GXiso:
	def main(self):
		dialog_main = DialogMain()
		dialog_main.show()
		gtk.main()




def find_data_dir():
	# search for our data :)
	dir = "."

	# current folder
	if os.path.exists(os.path.join(dir,"gxiso.glade")):
		return dir

	# executable folder
	dir, t = os.path.split(os.path.abspath(sys.argv[0]))

	if os.path.exists(os.path.join(dir,"gxiso.glade")):
		return dir

	# or system folder
	h, t = os.path.split(dir)
	if t == "bin":
		dir = os.path.join(h, "share")
		dir = os.path.join(dir, "gxiso")
		if os.path.exists(os.path.join(dir,"gxiso.glade")):
			return dir
	return None


def excepthook(type, value, tb):
	import StringIO, traceback
	trace = StringIO.StringIO()
	traceback.print_exception(type, value, tb, None, trace)
	print trace.getvalue()
	message = _(
	"<big><b>A programming error has been detected during the execution of this program.</b></big>"
	"\n\n<tt><small>%s</small></tt>") % trace.getvalue()
	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
		gtk.BUTTONS_OK, message)
	dialog.set_title(_("Bug Detected"))
	dialog.set_markup(message)
	dialog.run()
	dialog.hide()
	sys.exit(1)



if __name__ == "__main__":

	sys.excepthook = excepthook
	name = "gxiso"

	try:
		gtk.glade.bindtextdomain(name)
		gtk.glade.textdomain(name)
		gettext.install(name, unicode=1)
	except LookupError:
		#TODO: gettext fails on win32
		log("gettext error, disabling...")
		def _(str):
			return str

	DATADIR = find_data_dir()
	if DATADIR:
		saved_folder = os.getcwd()
		os.chdir(DATADIR)

		program = GXiso()
		program.main()

		os.chdir(saved_folder)
	else:
		show_error(_("Cannot find data folder, please file a bug"))
