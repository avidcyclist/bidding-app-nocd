import boto3
from flask import current_app, request, jsonify
import os
from twilio.rest import Client
from app.models import Listing, User, Notification, Bid
from app import db
from datetime import datetime
import logging
from uuid import uuid4
from functools import wraps
import jwt
from dotenv import load_dotenv

load_dotenv()

def get_s3_client():
    """
    Returns a boto3 S3 client. If running on AWS (Elastic Beanstalk), it will use the IAM Role.
    """
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY')
    )

def send_sms(to, message):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

    client = Client(account_sid, auth_token)
    try:
        message = client.messages.create(
            body=message,
            from_=twilio_number,
            to=to
        )
        print(f"SMS sent successfully: {message.sid}")
    except Exception as e:
        print(f"Failed to send SMS to {to}: {str(e)}")
        
        
logger = logging.getLogger(__name__)

def check_expired_listings():
    now = datetime.utcnow()
    logger.info(f"Running check_expired_listings at {now}")
    expired_listings = Listing.query.filter(Listing.end_time <= now, Listing.is_active == True).all()
    logger.info(f"Found {len(expired_listings)} expired listings")

    for listing in expired_listings:
        listing.is_active = False
        db.session.commit()

        seller = User.query.get(listing.user_id)
        if seller:
            send_sms(seller.phone_number, f"Your listing '{listing.title}' has ended.")
            seller_notification = Notification(
                user_id=listing.user_id,
                message=f"Your listing '{listing.title}' has ended.",
                is_read=False
            )
            db.session.add(seller_notification)

        highest_bid = Bid.query.filter_by(listing_id=listing.id).order_by(Bid.amount.desc()).first()
        if highest_bid:
            winner = User.query.get(highest_bid.user_id)
            if winner:
                send_sms(winner.phone_number, f"Congratulations! You won the listing '{listing.title}' with a bid of {highest_bid.amount}.")
                winner_notification = Notification(
                    user_id=highest_bid.user_id,
                    message=f"Congratulations! You won the listing '{listing.title}' with a bid of {highest_bid.amount}.",
                    is_read=False
                )
                db.session.add(winner_notification)

        db.session.commit()
    
    return f"{len(expired_listings)} listings expired and notifications sent."



def create_presigned_url(file_name, file_type):
    """
    Generate a pre-signed URL for uploading a file to S3.
    """
    try:
        s3 = boto3.client('s3')
        bucket = os.getenv('S3_BUCKET')
        region = os.getenv('S3_REGION')

        # Generate a unique file name
        unique_file_name = f"{uuid4().hex}_{file_name}"

        # Generate the pre-signed URL
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': unique_file_name,
                'ContentType': file_type
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )

        # Return the pre-signed URL and the file path
        return {
            "presigned_url": presigned_url,
            "file_path": f"https://{bucket}.s3.{region}.amazonaws.com/{unique_file_name}"
        }
    except Exception as e:
        raise Exception(f"Failed to generate pre-signed URL: {str(e)}")
    
def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            print("Missing token in request headers")  # Debugging log
            return jsonify({"error": "Missing token"}), 401

        try:
            # Remove "Bearer " prefix if present
            token = token.split(" ")[1] if " " in token else token
            print(f"Token to decode: {token}")  # Debugging log

            # Decode the JWT token using the SECRET_KEY from the app config
            decoded = jwt.decode(token, os.getenv['SECRET_KEY'], algorithms=["HS256"])
            print(f"Decoded token: {decoded}")  # Debugging log

            # Attach user_id to the request object for downstream use
            request.user_id = decoded["user_id"]
        except jwt.ExpiredSignatureError:
            print("Token has expired")  # Debugging log
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {str(e)}")  # Debugging log
            return jsonify({"error": "Invalid token"}), 401

        return func(*args, **kwargs)
    return wrapper
    
