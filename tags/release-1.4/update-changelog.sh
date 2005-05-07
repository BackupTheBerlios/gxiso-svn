#!/bin/sh

echo "# this file is generated from the subversion log. do not edit!" > ChangeLog
svn log | gnuify-changelog >> ChangeLog

head ChangeLog
