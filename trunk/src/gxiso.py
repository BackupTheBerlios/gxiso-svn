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
import pdb
import time
import string
import struct
import re
import thread
import md5
import pygtk
pygtk.require('2.0')
import gobject
import gtk
import gtk.glade
import gnome
import gettext
_=gettext.gettext

BUFFER_SIZE=1024*16

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

FILE_DIR = 0x10

HEADER_SIGNATURE = "MICROSOFT*XBOX*MEDIA"

def gtk_iteration():
	while gtk.events_pending():
		gtk.main_iteration(gtk.FALSE)

def read_unpack(file, format):
	buffer = file.read(struct.calcsize(format))
	return struct.unpack(format,buffer)

class ExtractError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

def show_error(message):
	dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, 
		gtk.BUTTONS_OK, message)
	dialog.run()
	dialog.hide()

def log(message):
	print message

	
total_size=0

class NullWriter:
	def init(self):
		pass
	def open(self, filename):
		pass
	def write(self, buffer):
		pass
	def close(self):
		pass
	def mkdir(self, name):
		pass
	def chdir(self, name):
		pass
	def quit(self):
		pass


class FileWriter:
	def __init__(self, base_folder):
		self.base_folder = base_folder
	def init(self):
		try:
			os.makedirs(self.base_folder)
		except OSError:
			pass
		self.chdir(self.base_folder)
		pass
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
			log( _("warning: cannot mkdir '%s'") % name)
	def chdir(self, name):
		try:
			os.chdir(name)
		except OSError:
			#raise ExtractError(_("cannot chdir '%s'") % name)
			log(_("cannot chdir '%s'") % name)
	def quit(self):
		pass

import ftplib

class FTPWriter:
	def __init__(self, ip, login, password, base_folder):
		self.ip = ip
		self.login = login
		self.password = password
		self.base_folder = base_folder

	def init(self):
		log("connecting to %s@%s" % (self.login,self.ip))
		try:
			self.session = ftplib.FTP(self.ip,self.login,self.password)
			self.chdir(self.base_folder)
		except ftplib.all_errors, detail:
			raise ExtractError(_("Cannot connect to xbox:\n"+detail[1]+"\n\nIs the xbox FTP server running?\nVerify address, login and password."))
			#raise
		self.lock = thread.allocate_lock()

	def quit(self):
		self.session.quit()

	def open(self, filename):
		self.buffer = ""
		self.closing = False
		#thread.start_new_thread(self.session.storbinary,("STOR %s" % filename, self))
		self.file = file("/tmp/gxiso.tmp","wb")
		self.filename = filename
		
	def write(self, buffer):
		#print "write: %d bytes in buffer, adding %d bytes" % (len(self.buffer), len(buffer))

		self.file.write(buffer)
	
		#while len(self.buffer) > 0:
			# wait buffer read
			#time.sleep(0.1)
		# append to buffer	
		
		#self.lock.acquire()
		#self.buffer += buffer
		#self.lock.release()
		
	def close(self):
		self.closing = True

		self.file.close
		self.file = file("/tmp/gxiso.tmp","rb")

		self.session.storbinary("STOR %s" % self.filename, self)

		self.file.close()

	def mkdir(self, name):
		try:
			#print "mkdir '%s'" % name
			self.session.mkd(name)
		except ftplib.error_reply:
			pass
		except ftplib.all_errors:
			print _("error mkdir '%s'") % name
	def chdir(self, name):
		try:
			#print "chdir '%s'" % name
			self.session.cwd(name)
		except ftplib.error_reply:
			pass
		except ftplib.all_errors:
			print _("error chdir '%s'") % name

	def read(self, size):
		#print "read: %d bytes in buffer, removing %d bytes" % (len(self.buffer), size)
		
		buffer = self.file.read(size)
		return buffer
		
		#while len(self.buffer) == 0:
			# wait buffer write
			#time.sleep(0.1)
			#if self.closing:
				#return ""
			
		#self.lock.acquire()
		#buffer = self.buffer[:size]
		#self.buffer = self.buffer[size:]
		#self.lock.release()

		#return buffer
		
		
	#import ftplib
	#session = ftplib.FTP('192.168.0.6','xbox','xbox')
	#test = Extract()
	#test.file = open('gxiso.py','rb')
	#session.cwd("/g/tmp")
	#session.storbinary('STOR yop.py', test)  
	#test.file.close()                                     
	#session.quit()                                         
	
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
	def quit(self):
		self.file.quit()
		self.ftp.quit()

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

	def write_file_parse(self,filename,size,sector):
		if filename == "default.xbe":
			# search xbe real name
			self.parse_xbe(sector)
		pass

	def write_file_real(self,filename,size,sector):
	
		self.current_file = filename
	
		self.iso.seek(sector*2048,SEEK_SET)
		self.writer.open(filename)
		
		buffer = "-"
		try:
			while buffer != "":
				#time.sleep(1)
				
				readsize = min(size,BUFFER_SIZE)
				buffer = self.iso.read(readsize)
				self.writer.write(buffer);
				size = size - readsize
				self.write_position += readsize
				if size<0: 
					break
				if self.canceled: 
					return
				while self.paused:
					time.sleep(0.1)
		finally:	
			self.writer.close()
		
	def parse_xbe(self,sector):
		self.iso.seek(sector*2048,SEEK_SET)
		self.iso.seek(0x190,SEEK_CUR)
		name = self.iso.read(80)

		self.xbe_name = ""
		
		for i in range(80):
			if name[i] != "\x00":
				self.xbe_name += name[i]
		

	def browse_file(self, sector, offset=0):
	
		if self.canceled: 
			return
		
		# jump to sector
		self.iso.seek(sector*2048+offset, SEEK_SET)
	
		# read file header
		ltable, rtable, newsector, filesize, attributes, filename_size \
		= read_unpack(self.iso, "<HHLLBB")
		
		# read file name
		filename = self.iso.read(filename_size)
		
		self.files = self.files + 1
		
		if attributes & FILE_DIR > 0:
			if filename_size > 0:
				# browse folder
				self.writer.mkdir(filename)
				self.writer.chdir(filename)
				self.browse_file(newsector)
				self.writer.chdir("..")
		else:
			self.size  = self.size + filesize
			self.write_file(filename,filesize,newsector);
	
		if rtable > 0:
			self.browse_file(sector,rtable*4)
		if ltable > 0:
			self.browse_file(sector,ltable*4)

	def extract(self,iso_name):
		# parse and extract iso
	
		saved_folder = os.getcwd()
		try:
			self.writer.init()
			self.write_file = self.write_file_real
			self.parse_internal(iso_name)
		except ExtractError, details:
			os.chdir(saved_folder)
			self.error = details.message
		os.chdir(saved_folder)


	def parse(self,iso_name):
		# only parse iso
		self.write_file = self.write_file_parse
		return self.parse_internal(iso_name)

	def parse_internal(self,iso_name):
		# internal parser

		self.files = 0
		self.size  = 0
		self.write_position=0

		log("opening xiso: "+iso_name);
		try:
			self.iso = open(iso_name, 'rb');
		except IOError:
			return "Cannot open '"+iso_name+"'"


		# skip beggining
		self.iso.seek(0x10000,SEEK_SET)
		
		# read and verify header
		header = self.iso.read(0x14)
		if header != HEADER_SIGNATURE:
			return "Not a valid xbox iso image"

		# read root sector address
		root_sector, = read_unpack(self.iso, "<L")
	
		# skip root_size + FILETIME + unused
		self.iso.seek(0x7d4,SEEK_CUR)
		
		# read and verify header
		header = self.iso.read(0x14)
		if header != HEADER_SIGNATURE:
			return "Not a valid xbox iso image"

		# and start extracting files
		self.browse_file(root_sector)

		return None

class Window:
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

	def stop(self):
		self.ui_dialog_progress.hide_all()

	def set_current_operation(self, operation):
		self.ui_label_operation.set_markup("<b>%s</b>" % operation)
		
	def set_current_file(self, filename, number, total):
		self.ui_label_detail.set_markup("<i>%s</i>" % filename)
		self.current_file = number
		self.total_files = total
		
	def pulse(self):
		self.ui_progressbar.pulse()
		
	def set_fraction(self, fraction):
		if self.paused: return
		
		self.ui_progressbar.set_fraction(fraction)
		now=time.time()
		if fraction<0.01: fraction = 0.01
		remaining = int((now-self.starttime) / fraction-(now-self.starttime))
		minutes = remaining/60
		if minutes<1:
			text = _("less than 1 minute left.")
		elif minutes==1:
			text = _("about 1 minute left.")
		else :
			text = _("about %d minutes left." % minutes)

		if self.paused:
			text = _("Paused")

		self.ui_progressbar.set_text(_("File %d/%d, %s") % 
			(self.current_file, self.total_files, text))

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
			"extract": True,
			"upload": True,
			"xbox_ip": "192.168.0.6",
			"xbox_login": "xbox",
			"xbox_password": "xbox",
			"xbox_drive": 2
		}
		self.settings = self.default_settings
		
		# widgets we will connect to
		self.ui_checkbutton_extract =\
		self.ui_checkbutton_upload =\
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
			log("cannot read "+filename)
			return 
			
		try:
			self.settings = eval(f.read(-1))
		except SyntaxError:
			pass
			
		f.close()
		self.settings_to_ui()	
		
	def save_settings(self):
	
		self.settings_from_ui()
		filename = os.path.expanduser("~/.gxiso")
		try:
			f = open(filename,"w")
			f.write( repr(self.settings) )
			f.close()
		except IOError:
			log("cannot write "+filename)

	def settings_to_ui(self):
		self.ui_checkbutton_extract.set_active(self.settings["extract"])
		self.ui_checkbutton_upload.set_active(self.settings["upload"])
		self.ui_entry_xbox_address.set_text(self.settings["xbox_ip"])
		self.ui_entry_xbox_login.set_text(self.settings["xbox_login"])
		self.ui_entry_xbox_password.set_text(self.settings["xbox_password"])
		self.ui_combobox_xbox_drive.set_active(self.settings["xbox_drive"])
	
	def settings_from_ui(self):
		self.settings["extract"] = self.ui_checkbutton_extract.get_active()
		self.settings["upload"] = self.ui_checkbutton_upload.get_active()
		self.settings["xbox_ip"] = self.ui_entry_xbox_address.get_text()
		self.settings["xbox_login"] = self.ui_entry_xbox_login.get_text()
		self.settings["xbox_password"] = self.ui_entry_xbox_password.get_text()
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
		error = xiso.parse(filename)
		if error:
			self.xbe_name = None
			self.ui_label_iso_infos.set_markup("<b>not a valid xbox iso image!</b>")
		else:
			self.xbe_name = xiso.xbe_name
			self.ui_label_iso_infos.set_markup("Title name: <b>%s</b> (%d MB)" %
			(self.xbe_name, os.path.getsize(filename)/(1024*1024)) )
			if self.ui_entry_folder.get_text() != "":
				self.ui_entry_folder.set_text(os.path.join(os.getcwd(),self.xbe_name))

	def extract_xiso(self):
		# get infos from ui
		filename = self.ui_entry_xiso.get_text()
		local_folder = self.ui_entry_folder.get_text()
		ftp_folder = "/g/tmp"
		ftp_ip = self.ui_entry_xbox_address.get_text()
		ftp_login = self.ui_entry_xbox_login.get_text()
		ftp_password = self.ui_entry_xbox_password.get_text()
		
		# init progress dialog
		progress = DialogProgress()
		progress.set_current_operation(_("Parsing"))
		gtk_iteration()

		# parse info from xiso
		xiso = XisoExtractor(NullWriter())
		error = xiso.parse(filename)
		if error:
			progress.stop()
			gtk_iteration()
			show_error(error)
			return
		size = xiso.size
		total_files = xiso.files

		# select writer plugin
		writer = NullWriter()
		extract = self.ui_checkbutton_extract.get_active()
		upload = self.ui_checkbutton_upload.get_active()
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
			progress.hide()
			return

		# and start the extraction thread
		if upload:
			progress.set_current_operation(_("Connecting to ftp://%s@%s")%
				(ftp_login, ftp_ip) )
		progress.start()
		xiso = XisoExtractor(writer)
		thread.start_new_thread(xiso.extract, (filename,))
		#xiso.extract(filename)

		while (xiso.write_position < size) and (not xiso.canceled) and (not xiso.error):
	
	
			fraction = float(xiso.write_position)/float(size)
	
			if xiso.write_position == 0:
				progress.pulse()
			else:
				progress.set_current_operation(operation)
				progress.set_current_file(xiso.current_file, xiso.files, total_files)
				progress.set_fraction(fraction)

			xiso.canceled = progress.canceled
			xiso.paused = progress.paused

			gtk_iteration()
			time.sleep(0.1)

		if xiso.error:
			show_error(xiso.error)

		print _("done, %.2f MiB/s)") % (size/(time.time()-progress.starttime)/(1024*1024))
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
		dialog = gtk.FileChooserDialog(_("Open Xbox Iso"),None,
			action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

		filter = gtk.FileFilter()
		filter.add_pattern("*.iso")

		dialog.set_filter(filter)

		dialog.show_all()
		result = dialog.run()
		dialog.hide_all()	
		if result == gtk.RESPONSE_OK:
			self.ui_entry_xiso.set_text(dialog.get_filename())
			self.get_iso_infos(dialog.get_filename())
			if (self.xbe_name):
				self.ui_entry_folder.set_text(os.path.join(os.getcwd(),self.xbe_name))

	def on_button_folder_browse_clicked(self, widget):
		dialog = gtk.FileChooserDialog(_("Select Extract Folder"),None,
			action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER, buttons=(gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

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


if __name__ == "__main__":

	program = GXiso()
	program.main()
