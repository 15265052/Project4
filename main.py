
import ftplib

with ftplib.FTP('ftp.ncnu.edu.tw') as ftp:

    try:
        ftp.login()

        files = []
        ftp.dir()


    except ftplib.all_errors as e:
        print('FTP error:', e)
