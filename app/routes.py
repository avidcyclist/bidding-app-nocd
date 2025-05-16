from flask import Blueprint, jsonify, request
from app.models import User, Listing, Bid, Notification
from app import db
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import boto3
from uuid import uuid4
from flask import current_app
from app.utils import get_s3_client, send_sms, check_expired_listings
import os


main = Blueprint('main', __name__)


@main.route('/')
def home():
    try:
        # query: Fetch all users
        users = User.query.all()
        #Return a JSON response with user data
        return jsonify({"users": [user.username for user in users]})
    except Exception as e:
        # Handle any exceptions that occur during the query
        return jsonify({"error": str(e)})
   
   
   
# Fetch all listings  
@main.route('/listings', methods=['GET'])
def get_listings():
    try:
        # Fetch all listings
        listings = Listing.query.all()
        # Return a JSON response with listing data, including image URLs
        return jsonify({
            "listings": [
                {
                    "id": listing.id,
                    "title": listing.title,
                    "description": listing.description,
                    "starting_price": listing.starting_price,
                    "current_price": listing.current_price,
                    "end_time": listing.end_time,
                    "user_id": listing.user_id,
                    "image_url": listing.image_url  # Include the image URL
                }
                for listing in listings
            ]
        })
    except Exception as e:
        # Handle any exceptions that occur during the query
        return jsonify({"error": str(e)}), 400
    
# Allow users to create a new listing
# Adds details to the listing, such as title, description, starting price, current price, end time, and user ID.
@main.route('/listings', methods=['POST'])
def create_listing():
    S3_BUCKET = current_app.config['S3_BUCKET']
    S3_REGION = current_app.config['S3_REGION']
    S3_BASE_URL = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com"

    image_url = None  # Default to None if no image is provided

    # Handle file uploads
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            filename = f"{uuid4().hex}_{secure_filename(file.filename)}"
            s3 = get_s3_client()
            try:
                s3.upload_fileobj(
                    file,
                    S3_BUCKET,
                    filename,
                    ExtraArgs={"ContentType": file.content_type}
                )
                image_url = f"{S3_BASE_URL}/{filename}"
            except Exception as e:
                return jsonify({"error": f"Failed to upload image to S3: {str(e)}"}), 500

    # Handle JSON or form data
    data = request.get_json() or request.form  # Support both JSON and form data
    try:
        new_listing = Listing(
            title=data['title'],
            description=data['description'],
            starting_price=data['starting_price'],
            current_price=data['starting_price'],
            end_time=data['end_time'],
            user_id=data['user_id'],
            image_url=image_url  # Include the uploaded image URL
        )
        db.session.add(new_listing)
        db.session.commit()
        return jsonify({"message": "Listing created successfully!", "image_url": image_url}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
     

# Fetch specific listing by ID
@main.route('/listings/<int:id>', methods=['GET'])
def get_listing(id):
    try:
        # Fetch the listing by ID
        listing = Listing.query.get(id)
        if not listing:
            # If the listing is not found, return a 404 error
            return jsonify({"error": "Listing not found"}), 404
        # Return a JSON response with listing details, including the image URL
        return jsonify({
            "id": listing.id,
            "title": listing.title,
            "description": listing.description,
            "starting_price": listing.starting_price,
            "current_price": listing.current_price,
            "end_time": listing.end_time,
            "user_id": listing.user_id,
            "image_url": listing.image_url  # Include the image URL
        })
    except Exception as e:
        # Handle any exceptions that occur during the query
        return jsonify({"error": str(e)}), 400
    
# Post a Bid
@main.route('/bids', methods=['POST'])
def place_bid():
    data = request.get_json()
    try:
        # Fetch the listing
        listing = Listing.query.get(data['listing_id'])
        if not listing:
            return jsonify({"error": "Listing not found"}), 404

        # Validate the bid amount > current price
        if data['amount'] <= listing.current_price:
            return jsonify({"error": "Bid must be higher than the current price"}), 400

        # Fetch the previous highest bid (if any)
        previous_highest_bid = Bid.query.filter_by(listing_id=data['listing_id']).order_by(Bid.amount.desc()).first()

        # Check if the bidder is the seller
        if listing.user_id == data['user_id']:
            return jsonify({"error": "You cannot bid on your own listing."}), 400

        # Check if the user is outbidding themselves
        if previous_highest_bid and previous_highest_bid.user_id == data['user_id']:
            pass  # Skip notification if the user is outbidding themselves
        else:
            # Notify the seller
            seller = User.query.get(listing.user_id)  # Fetch the seller's details
            seller_notification = Notification(
                user_id=listing.user_id,
                message=f"A new bid has been placed on your listing: {listing.title}",
                is_read=False
            )
            db.session.add(seller_notification)

            # Notify the seller via SMS
            if seller and seller.phone_number:
                send_sms(seller.phone_number, f"A new bid has been placed on your listing: {listing.title}")
            else:
                print("Seller does not have a valid phone number.")

            # Notify the previous highest bidder (if applicable)
            if previous_highest_bid:
                previous_bidder = User.query.get(previous_highest_bid.user_id)  # Fetch the previous bidder's details
                if previous_bidder.id != data['user_id']:  # Ensure the current bidder is not the previous bidder
                    outbid_notification = Notification(
                        user_id=previous_highest_bid.user_id,
                        message=f"You have been outbid on {listing.title}.",
                        is_read=False
                    )
                    db.session.add(outbid_notification)

                    # Notify the previous highest bidder via SMS
                    if previous_bidder and previous_bidder.phone_number:
                        send_sms(previous_bidder.phone_number, f"You have been outbid on {listing.title}.")
                    else:
                        print("Previous bidder does not have a valid phone number.")

        # Create the new bid object
        new_bid = Bid(
            amount=data['amount'],
            user_id=data['user_id'],
            listing_id=data['listing_id']
        )
        db.session.add(new_bid)

        # Update the current price of the listing
        listing.current_price = data['amount']
        db.session.commit()

        return jsonify({"message": "Bid placed successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
# Get all bids for a specific listing    
@main.route('/bids/<int:listing_id>', methods=['GET'])
def get_bids_for_listing(listing_id):
    try:
        # Fetch the listing by ID
        listing = Listing.query.get(listing_id)
        if not listing:
            return jsonify({"error": "Listing not found"}), 404

        # Fetch all bids for the listing
        bids = Bid.query.filter_by(listing_id=listing_id).all()
        # Return a JSON response with bid details
        return jsonify({
            "listing_id": listing_id,
            "bids": [
                {
                    "id": bid.id,
                    "amount": bid.amount,
                    "user_id": bid.user_id,
                    "timestamp": bid.timestamp
                }
                for bid in bids
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
# Fetch all notifications for a specific user
@main.route('/notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    try:
        # Fetch all notifications for the user
        notifications = Notification.query.filter_by(user_id=user_id).all()
        # Return a JSON response with notification details
        return jsonify({
            "user_id": user_id,
            "notifications": [
                {
                    "id": notification.id,
                    "message": notification.message,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at
                }
                for notification in notifications
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
    
# Create a notification
@main.route('/notifications', methods=['POST'])
def create_notification():

    data = request.get_json()
    try:
        # Create a new notification object
        new_notification = Notification(
            user_id=data['user_id'],
            message=data['message'],
            is_read=False  # Default to unread
        )
        # Add the notification to the database
        db.session.add(new_notification)
        db.session.commit()
        return jsonify({"message": "Notification created successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
#@main.route('/debug-env', methods=['GET'])
#def debug_env():
#    return jsonify({
#        "SQLALCHEMY_DATABASE_URI": os.environ.get('SQLALCHEMY_DATABASE_URI'),
#        "S3_BUCKET": os.environ.get('S3_BUCKET'),
#        "S3_REGION": os.environ.get('S3_REGION'),
#        "TWILIO_ACCOUNT_SID": os.environ.get('TWILIO_ACCOUNT_SID'),
#        "TWILIO_AUTH_TOKEN": os.environ.get('TWILIO_AUTH_TOKEN'),
#        "TWILIO_PHONE_NUMBER": os.environ.get('TWILIO_PHONE_NUMBER'),
#    })



@main.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    try:
        new_user = User(
            username=data['username'],
            email=data['email'],
            phone_number=data['phone_number'],  # Require phone number
            password_hash=generate_password_hash(data['password'])
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    

  
@main.route('/check-expired', methods=['POST'])
def check_expired():
    try:
        result = check_expired_listings()
        return jsonify({"message": "Checked for expired listings", "result": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/listings/<int:id>/bids', methods=['GET'])
def listing_bid_history(id):
    try:
        bids = Bid.query.filter_by(listing_id=id).order_by(Bid.timestamp).all()
        return jsonify([
            {
                "id": bid.id,
                "amount": bid.amount,
                "user_id": bid.user_id,
                "timestamp": bid.timestamp
            }
            for bid in bids
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@main.route('/listings/<int:id>/highest_bid', methods=['GET'])
def listing_highest_bid(id):
    try:
        bid = Bid.query.filter_by(listing_id=id).order_by(Bid.amount.desc()).first()
        if not bid:
            return jsonify({"id": None, "amount": None, "user_id": None, "timestamp": None}), 200
        return jsonify({
            "id": bid.id,
            "amount": bid.amount,
            "user_id": bid.user_id,
            "timestamp": bid.timestamp
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@main.route('/notifications/<int:id>/read', methods=['PATCH'])
def mark_notification_read(id):
    try:
        n = Notification.query.get_or_404(id)
        n.is_read = True
        db.session.commit()
        return jsonify({"message": "Marked read"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400










