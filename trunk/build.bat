@echo off

del /F /S /Q build dist > nul
python.exe setup.py py2exe

copy "%GTK_BASEPATH%\bin\libpng12.dll" dist\
copy "%GTK_BASEPATH%\bin\zlib1.dll" dist\
copy "%GTK_BASEPATH%\bin\libpangoft2-1.0-0.dll" dist\
copy "%GTK_BASEPATH%\bin\libxml2.dll" dist\

mkdir dist\etc\pango
copy "%GTK_BASEPATH%\etc\pango" dist\etc\pango

mkdir dist\etc\gtk-2.0\
copy "%GTK_BASEPATH%\etc\gtk-2.0\gdk-pixbuf.loaders" dist\etc\gtk-2.0

mkdir dist\lib\gtk-2.0\2.4.0\loaders
copy "%GTK_BASEPATH%\lib\gtk-2.0\2.4.0\loaders\libpixbufloader-png.dll" dist\lib\gtk-2.0\2.4.0\loaders
copy "%GTK_BASEPATH%\lib\gtk-2.0\2.4.0\loaders\libpixbufloader-xpm.dll" dist\lib\gtk-2.0\2.4.0\loaders
copy "%GTK_BASEPATH%\lib\gtk-2.0\2.4.0\loaders\libpixbufloader-ico.dll" dist\lib\gtk-2.0\2.4.0\loaders

mkdir dist\lib\pango\1.4.0\modules
copy "%GTK_BASEPATH%\lib\pango\1.4.0\modules\pango-basic-win32.dll" dist\lib\pango\1.4.0\modules\
copy "%GTK_BASEPATH%\lib\pango\1.4.0\modules\pango-basic-fc.dll" dist\lib\pango\1.4.0\modules\

copy "%GTK_BASEPATH%\lib\locale" dist\lib\

copy "%GTK_BASEPATH%\etc\gtk-2.0\gtkrc" dist\etc\gtk-2.0
mkdir dist\lib\gtk-2.0\2.4.0\engines"
copy "%GTK_BASEPATH%\lib\gtk-2.0\2.4.0\engines\libwimp.dll" dist\lib\gtk-2.0\2.4.0\engines
mkdir dist\share\themes\wimp\gtk-2.0"
copy "%GTK_BASEPATH%\share\themes\wimp\gtk-2.0\gtkrc" dist\share\themes\wimp\gtk-2.0

rem disabled as the resulting setup.exe is bigger :)
rem upx --best --force dist\*.exe dist\*.dll dist\*.pyd

rem disabled as it breaks all
rem strip  dist/*.exe dist/*.dll dist/*.pyd

"C:\Program Files\NSIS\makensis.exe" gxiso.nsi
