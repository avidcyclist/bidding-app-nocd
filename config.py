
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Use environment variable
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')  # Use environment variable for RDS
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable to save resources

    S3_BUCKET = os.environ.get('S3_BUCKET')  # Use environment variable
    S3_REGION = os.environ.get('S3_REGION')  # Use environment variable

    
