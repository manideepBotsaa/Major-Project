"""Shared extension instances.

Kept in a separate module so models, routes, and services can import ``db``
without importing the application factory (and creating circular imports).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
