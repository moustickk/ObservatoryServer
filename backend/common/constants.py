APP_NAME = "ObservatoryServer"

VERSION = "3.0.0-alpha"

# Format des journaux. La date complete est necessaire : un fichier qui ne
# contient que l'heure est inutilisable des le lendemain.
LOG_DATE_FORMAT = "%d-%m-%Y %H:%M:%S"

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"

LOG_ACCESS_FORMAT = '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
