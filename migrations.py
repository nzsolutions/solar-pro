"""
SolarPro Energy Management System — Central Database Migration & Schema Registry
================================================================================
File: migrations.py
Database: solar_project (MySQL)

PURPOSE:
  This file serves as the centralized master registry of all database tables, columns,
  data types, constraints, and chronological migration events for the SolarPro application.

MAINTENANCE GUIDELINES (GOING FORWARD):
  1. NEW TABLE CREATION:
     - Add the new table definition with its full column specification under SECTION 2.
     - Append a new entry under SECTION 3 (CHRONOLOGICAL MIGRATION TIMELINE).
  2. COLUMN / SCHEMA MODIFICATIONS (ADD, MODIFY, DROP COLUMN, INDEXES):
     - Update the target table in SECTION 2 to reflect the latest schema state.
     - Append a change-record entry in SECTION 3 describing the exact change, date, and app migration.
  3. NO DUPLICATE ENTRIES:
     - Each migration version ID must be unique.
"""

from datetime import datetime

DATABASE_NAME = "solar_project"
DATABASE_ENGINE = "mysql"
LAST_AUDITED = "2026-11-16"

# ==============================================================================
# SECTION 1: DATABASE SUMMARY STATISTICS
# ==============================================================================
SCHEMA_METRICS = {
    "total_tables": 34,
    "application_tables_count": 24,
    "django_core_tables_count": 10,
    "total_columns": 260,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci"
}

# ==============================================================================
# SECTION 2: COMPLETE TABLE AND COLUMN SCHEMA SPECIFICATIONS
# ==============================================================================
TABLES_SCHEMA = {
    "access_controls": {
        "table_name": "access_controls",
        "column_count": 6,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "role_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "menu_key",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "permissions",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "activity_master": {
        "table_name": "activity_master",
        "column_count": 13,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "activity_title",
                "type": "varchar(255)",
                "nullable": False,
                "key": "UNI",
                "default": None,
                "extra": ""
            },
            {
                "name": "activity_category",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "description",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "default_frequency",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "estimated_duration",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "photo_required",
                "type": "tinyint(1)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(20)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "added_by",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime(6)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime(6)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "form_id",
                "type": "bigint",
                "nullable": True,
                "key": "MUL",
                "default": None,
                "extra": ""
            },
        ]
    },
    "admin_user": {
        "table_name": "admin_user",
        "column_count": 7,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "email",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "password",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_admin",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "assigned_stock": {
        "table_name": "assigned_stock",
        "column_count": 11,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "project_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "item_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "qty",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "used_qty",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "grn_number",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "received_by",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "date",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "notes",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "attendance_master": {
        "table_name": "attendance_master",
        "column_count": 8,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "working_hours",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "required_working_hours",
                "type": "varchar(50)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "latitude",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "longitude",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_group": {
        "table_name": "auth_group",
        "column_count": 2,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "name",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_group_permissions": {
        "table_name": "auth_group_permissions",
        "column_count": 3,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "group_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "permission_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_permission": {
        "table_name": "auth_permission",
        "column_count": 4,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "content_type_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "codename",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_user": {
        "table_name": "auth_user",
        "column_count": 11,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "password",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "last_login",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_superuser",
                "type": "tinyint(1)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "username",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "last_name",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "email",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_staff",
                "type": "tinyint(1)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_active",
                "type": "tinyint(1)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "date_joined",
                "type": "datetime",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "first_name",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_user_groups": {
        "table_name": "auth_user_groups",
        "column_count": 3,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "user_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "group_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "auth_user_user_permissions": {
        "table_name": "auth_user_user_permissions",
        "column_count": 3,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "user_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "permission_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "dashboard_configs": {
        "table_name": "dashboard_configs",
        "column_count": 5,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "config_json",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "department_master": {
        "table_name": "department_master",
        "column_count": 6,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "department_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "added_by",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "designation_master": {
        "table_name": "designation_master",
        "column_count": 7,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "designation_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "department_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "added_by",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "django_admin_log": {
        "table_name": "django_admin_log",
        "column_count": 8,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "object_id",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "object_repr",
                "type": "varchar(20)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "action_flag",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "change_message",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "content_type_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "user_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "action_time",
                "type": "datetime",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "django_content_type": {
        "table_name": "django_content_type",
        "column_count": 3,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "app_label",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "model",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "django_migrations": {
        "table_name": "django_migrations",
        "column_count": 4,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "app",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "applied",
                "type": "datetime",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "django_session": {
        "table_name": "django_session",
        "column_count": 3,
        "columns": [
            {
                "name": "session_key",
                "type": "varchar(255)",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": ""
            },
            {
                "name": "session_data",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "expire_date",
                "type": "datetime",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "document_master": {
        "table_name": "document_master",
        "column_count": 6,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "type_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "dynamic_dashboard_section_master": {
        "table_name": "dynamic_dashboard_section_master",
        "column_count": 5,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "section_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "dynamic_forms": {
        "table_name": "dynamic_forms",
        "column_count": 9,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "form_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "description",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "project_ids",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "form_schema",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_active",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "emp_attendance": {
        "table_name": "emp_attendance",
        "column_count": 9,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "employee_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "punch_in",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "punch_out",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "latitude",
                "type": "decimal(12,2)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "longitude",
                "type": "decimal(12,2)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "actual_worked",
                "type": "varchar(50)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "employee_otps": {
        "table_name": "employee_otps",
        "column_count": 6,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "employee_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "otp",
                "type": "varchar(10)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "expires_at",
                "type": "datetime",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "employees": {
        "table_name": "employees",
        "column_count": 21,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "role",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "app_username",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "app_password",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "email",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "phone",
                "type": "varchar(50)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "gender",
                "type": "varchar(20)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "dob",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "address",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "city",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "state",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "pincode",
                "type": "varchar(20)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "joining_date",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "relieving_date",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "documents",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "fcm_token",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "expenses": {
        "table_name": "expenses",
        "column_count": 13,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "employee_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "project_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "category_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "amount",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "date",
                "type": "date",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "emp_comment",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "image",
                "type": "varchar(500)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "rejection_reason",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "expenses_category_master": {
        "table_name": "expenses_category_master",
        "column_count": 5,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "category_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "form_submissions": {
        "table_name": "form_submissions",
        "column_count": 8,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "form_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "project_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "emp_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "submission_data",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "leads": {
        "table_name": "leads",
        "column_count": 11,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "client_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "location",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "source",
                "type": "varchar(100)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "system_size",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "value",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "assigned_to",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "opening_stock": {
        "table_name": "opening_stock",
        "column_count": 10,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "item_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "category",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "quantity",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "unit",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "rate",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "low_stock_threshold",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "project_document": {
        "table_name": "project_document",
        "column_count": 7,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "project_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "document_type_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "file",
                "type": "varchar(500)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "name",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "projects": {
        "table_name": "projects",
        "column_count": 14,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "client_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "site_id",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "site_manager",
                "type": "int",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "field_staff",
                "type": "longtext",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "status",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "start_date",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "end_date",
                "type": "date",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "reporting_frequency",
                "type": "varchar(50)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "notes",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "project_name",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "site_master": {
        "table_name": "site_master",
        "column_count": 10,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "site_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "site_address",
                "type": "longtext",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "contact_number",
                "type": "varchar(50)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "latitude",
                "type": "decimal(12,2)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "longitude",
                "type": "decimal(12,2)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "radius",
                "type": "decimal(12,2)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "smtp_configuration": {
        "table_name": "smtp_configuration",
        "column_count": 13,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "config_name",
                "type": "varchar(255)",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "smtp_host",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "smtp_port",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "smtp_user",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "smtp_pass",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "smtp_crypto",
                "type": "varchar(50)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "from_email",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "from_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "is_default",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
    "stock_categories": {
        "table_name": "stock_categories",
        "column_count": 6,
        "columns": [
            {
                "name": "id",
                "type": "bigint",
                "nullable": False,
                "key": "PRI",
                "default": None,
                "extra": "auto_increment"
            },
            {
                "name": "company_id",
                "type": "int",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "category_name",
                "type": "varchar(255)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "added_by",
                "type": "varchar(100)",
                "nullable": False,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "created_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
            {
                "name": "updated_at",
                "type": "datetime",
                "nullable": True,
                "key": "",
                "default": None,
                "extra": ""
            },
        ]
    },
}

# ==============================================================================
# SECTION 3: CHRONOLOGICAL MIGRATION & REVISION TIMELINE
# ==============================================================================
MIGRATION_HISTORY = [
    {
        "app": "contenttypes",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "admin",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "admin",
        "migration_name": "0002_logentry_remove_auto_add",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "admin",
        "migration_name": "0003_logentry_add_action_flag_choices",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "contenttypes",
        "migration_name": "0002_remove_content_type_name",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0002_alter_permission_name_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0003_alter_user_email_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0004_alter_user_username_opts",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0005_alter_user_last_login_null",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0006_require_contenttypes_0002",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0007_alter_validators_add_error_messages",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0008_alter_user_username_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0009_alter_user_last_name_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0010_alter_group_name_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0011_update_proxy_permissions",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "auth",
        "migration_name": "0012_alter_user_first_name_max_length",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "authentication",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "dynamic_forms",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "employees",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "expenses",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "inventory",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "masters",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "operations",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "sessions",
        "migration_name": "0001_initial",
        "applied_at": "2026-10-30 08:07:45",
    },
    {
        "app": "operations",
        "migration_name": "0002_add_project_name_to_project",
        "applied_at": "2026-11-04 08:26:35",
    },
    {
        "app": "masters",
        "migration_name": "0002_activitymaster",
        "applied_at": "2026-11-12 06:04:02",
    },
]

# ==============================================================================
# SECTION 4: HELPER UTILITIES
# ==============================================================================
def get_table_schema(table_name: str) -> dict:
    """Retrieve the registered schema definition for a specific table."""
    return TABLES_SCHEMA.get(table_name)

def get_all_tables() -> list:
    """List all tracked database table names."""
    return sorted(list(TABLES_SCHEMA.keys()))

def has_column(table_name: str, column_name: str) -> bool:
    """Check if a table has a specific column."""
    schema = get_table_schema(table_name)
    if not schema:
        return False
    return any(col["name"] == column_name for col in schema.get("columns", []))

