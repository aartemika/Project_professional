"""Регистрация всех таблиц базы данных."""
from ..db_session import db
from .users_model import User
from .cities_model import City
from .categories_model import Category
from .work_formats_model import WorkFormat
from .vacancies_model import Vacancy
from .imports_model import ImportLog
