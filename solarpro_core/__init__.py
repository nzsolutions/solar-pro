import pymysql

pymysql.install_as_MySQLdb()

# Django 5/6 version check bypass to support MySQL 8.0.x
try:
    from django.db.backends.base.base import BaseDatabaseWrapper
    BaseDatabaseWrapper.check_database_version_supported = lambda self: None
except Exception:
    pass
