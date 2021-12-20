
import ftplib

with ftplib.FTP('ftp.sjtu.edu.cn') as ftp:

    try:
        ftp.login()

        files = []

        print(ftp.dir())
    except ftplib.all_errors as e:
        print('FTP error:', e)
