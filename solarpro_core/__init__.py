import pymysql

pymysql.install_as_MySQLdb()

# Enable Django to connect smoothly to MySQL 8.0.x
from django.db.backends.base.base import BaseDatabaseWrapper
BaseDatabaseWrapper.check_database_version_supported = lambda self: None
