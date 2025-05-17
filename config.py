#class Config:
#    SECRET_KEY = '026a09a53563d914169373613b947083'  # Replace with a secure key
#    MYSQL_HOST = 'bidding-app-db.cctaq8qo0d28.us-east-1.rds.amazonaws.com'  # Your RDS endpoint
#    MYSQL_USER = 'admin'  # Your RDS username
#    MYSQL_PASSWORD = '6hSKg4q3viqfmOxnw7ae'  # Your RDS password
#    MYSQL_DB = 'bidding_app'  # Your database name


import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Use environment variable
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')  # Use environment variable for RDS
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable to save resources

    S3_BUCKET = os.environ.get('S3_BUCKET')  # Use environment variable
    S3_REGION = os.environ.get('S3_REGION')  # Use environment variable

    
