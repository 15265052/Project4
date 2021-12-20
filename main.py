
import ftplib

with ftplib.FTP('ftp.sjtu.edu.cn') as ftp:

    try:
        ftp.login()

        files = []
        ftp.dir(files.append)
        print()

    except ftplib.all_errors as e:
        print('FTP error:', e)
