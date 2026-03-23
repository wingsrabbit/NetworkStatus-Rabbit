import os
from datetime import timedelta


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(BASE_DIR), 'data'))

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # SQLite
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DATA_DIR, 'networkstatus.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = SECRET_KEY
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'false').lower() == 'true'
    JWT_COOKIE_SAMESITE = 'Strict'
    JWT_ACCESS_COOKIE_PATH = '/'
    JWT_COOKIE_CSRF_PROTECT = False  # SameSite=Strict is sufficient
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # InfluxDB
    INFLUXDB_URL = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
    INFLUXDB_TOKEN = os.environ.get('INFLUXDB_TOKEN', '')
    INFLUXDB_ORG = os.environ.get('INFLUXDB_ORG', 'networkstatus')
    INFLUXDB_BUCKET_RAW = os.environ.get('INFLUXDB_BUCKET_RAW', 'raw')
    INFLUXDB_BUCKET_1M = os.environ.get('INFLUXDB_BUCKET_1M', 'agg_1m')
    INFLUXDB_BUCKET_1H = os.environ.get('INFLUXDB_BUCKET_1H', 'agg_1h')
