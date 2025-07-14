from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from models import User, Permission, Colaborador, Empresa, Setor, PresencaSalva
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, date, timedelta
from functools import wraps
import logging
import io
from sqlalchemy import func

app = Flask(__name__)

app.config['SECRET_KEY'] = 'admin_anderson_luft'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(debug=True)