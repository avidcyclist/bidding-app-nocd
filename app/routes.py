from flask import Blueprint, jsonify, request
from app.models import User, Listing, Bid, Notification
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
from flask import current_app
from app.utils import get_s3_client, send_sms, check_expired_listings, create_presigned_url, require_auth
import os
from datetime import datetime, timedelta
import jwt

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
                    "image_url": listing.image_url,  # Include the image URL
                    "is_active": listing.is_active
                }
                for listing in listings
            ]
        })
    except Exception as e:
        # Handle any exceptions that occur during the query
        return jsonify({"error": str(e)}), 400
    
# Allow users to create a new listing
@main.route('/listings', methods=['POST'])
@require_auth
def create_listing():
    print(f"Content-Type: {request.content_type}")

    try:
        # Use the authenticated user's ID
        user_id = request.user_id
        # Log the raw JSON data
        data = request.get_json()
        print(f"Raw JSON Data: {data}")

        # Extract fields from the request
        title = data.get('title')
        description = data.get('description')
        starting_price = data.get('starting_price')
        end_time = data.get('end_time')
        user_id = data.get('user_id')
        image_url = data.get('image_url')  # Pre-signed S3 URL

        # Log extracted fields
        print(f"Extracted Fields: title={title}, description={description}, starting_price={starting_price}, end_time={end_time}, user_id={user_id}, image_url={image_url}")

        # Validate required fields
        missing = [field for field in ['title', 'description', 'starting_price', 'end_time', 'user_id'] if not data.get(field)]
        if missing:
            print(f"Missing Fields: {missing}")
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        # Save the listing to the database
        try:
            listing = Listing(
                title=title,
                description=description,
                starting_price=starting_price,
                current_price=starting_price,
                end_time=end_time,
                user_id=user_id,
                image_url=image_url  # Save the S3 file path
            )
            db.session.add(listing)
            db.session.commit()

            # Log successful database save
            print(f"Listing created successfully with ID: {listing.id}")

            return jsonify({
                "message": "Listing created successfully!",
                "listing_id": listing.id,
                "image_url": image_url
            }), 201

        except Exception as e:
            # Log database error
            print(f"Database Error: {str(e)}")
            return jsonify({"error": f"Database error: {str(e)}"}), 500

    except Exception as e:
        # Log general error
        print(f"Error in create_listing: {str(e)}")
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

     

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
            "image_url": listing.image_url #Include the image URL
             
        })
    except Exception as e:
        # Handle any exceptions that occur during the query
        return jsonify({"error": str(e)}), 400
    
# Post a Bid
@main.route('/bids', methods=['POST'])
@require_auth
def place_bid():
    data = request.get_json()
    try:
        # Use the authenticated user's ID
        user_id = request.user_id
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
        if listing.user_id == user_id:
            return jsonify({"error": "You cannot bid on your own listing."}), 400

        # Check if the user is outbidding themselves
        if previous_highest_bid and previous_highest_bid.user_id == user_id:
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
            user_id=user_id,
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

        # Prepare the bid history
        bid_history = [
            {
                "id": None,  # No ID for the starting price
                "amount": listing.starting_price,
                "user_id": listing.user_id,  # The seller's user ID
                "timestamp": listing.created_at  # Use the listing creation time
            }
        ] + [
            {
                "id": bid.id,
                "amount": bid.amount,
                "user_id": bid.user_id,
                "timestamp": bid.timestamp
            }
            for bid in bids
        ]

        # Return the bid history
        return jsonify({
            "listing_id": listing_id,
            "bids": bid_history
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
# Fetch all notifications for a specific user
@main.route('/notifications/<int:user_id>', methods=['GET'])
@require_auth
def get_notifications(user_id):
    try:
        # Ensure the authenticated user is accessing their own notifications
        if user_id != request.user_id:
            return jsonify({"error": "Unauthorized access"}), 403

        # Fetch all notifications for the user
        notifications = Notification.query.filter_by(user_id=user_id).all()
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
@require_auth
def create_notification():
    data = request.get_json()
    try:
        # Use the authenticated user's ID
        user_id = request.user_id

        # Create a new notification object
        new_notification = Notification(
            user_id=user_id,
            message=data['message'],
            is_read=False  # Default to unread
        )
        db.session.add(new_notification)
        db.session.commit()
        return jsonify({"message": "Notification created successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    
@main.route('/debug-env', methods=['GET'])

def debug_env():
    return jsonify({
        "SQLALCHEMY_DATABASE_URI": os.environ.get('SQLALCHEMY_DATABASE_URI'),
        "S3_BUCKET": os.environ.get('S3_BUCKET'),
        "S3_REGION": os.environ.get('S3_REGION'),
        "TWILIO_ACCOUNT_SID": os.environ.get('TWILIO_ACCOUNT_SID'),
        "TWILIO_AUTH_TOKEN": os.environ.get('TWILIO_AUTH_TOKEN'),
        "TWILIO_PHONE_NUMBER": os.environ.get('TWILIO_PHONE_NUMBER'),
        "SECRET_KEY": os.environ.get('SECRET_KEY'),
    })

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
        
        # Fetch the listing
        listing = Listing.query.get(id)
        if not listing:
            return jsonify({"error": "Listing not found"}), 404

        
        
        bid = Bid.query.filter_by(listing_id=id).order_by(Bid.amount.desc()).first()
        if not bid:
            return jsonify({"id": None, "amount": listing.current_price, "user_id": None, "timestamp": None}), 200
        return jsonify({
            "id": bid.id,
            "amount": bid.amount,
            "user_id": bid.user_id,
            "timestamp": bid.timestamp
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@main.route('/notifications/<int:id>/read', methods=['PATCH'])
@require_auth
def mark_notification_read(id):
    try:
        # Fetch the notification
        notification = Notification.query.get_or_404(id)

        # Ensure the authenticated user owns the notification
        if notification.user_id != request.user_id:
            return jsonify({"error": "Unauthorized access"}), 403

        # Mark the notification as read
        notification.is_read = True
        db.session.commit()
        return jsonify({"message": "Marked read"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@main.route('/generate-presigned-url', methods=['POST'])
@require_auth
def generate_presigned_url():
    data = request.get_json()
    file_name = data.get('file_name')
    file_type = data.get('file_type')

    if not file_name or not file_type:
        return jsonify({'error': 'Missing file_name or file_type'}), 400

    try:
        # Call the utility function to generate the pre-signed URL
        result = create_presigned_url(file_name, file_type)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
@main.route('/debug-routes', methods=['GET'])
@require_auth
def debug_routes():
    from flask import current_app
    return jsonify([str(rule) for rule in current_app.url_map.iter_rules()])


@main.route('/users/register', methods=['POST'])
def register_user():
    data = request.get_json()
    try:
        # Check if the username or email already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({"error": "Username already exists"}), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({"error": "Email already exists"}), 400

        # Create a new user with a consistent hashing algorithm
        hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
        print(f"Generated password hash: {hashed_password}")  # Debugging log
        new_user = User(
            username=data['username'],
            email=data['email'],
            phone_number=data.get('phone_number'),  # Optional
            password_hash=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "User registered successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@main.route('/users/login', methods=['POST'])
def login_user():
    data = request.get_json()
    try:
        # Find the user by username
        user = User.query.filter_by(username=data['username']).first()
        if not user:
            print("User not found")  # Debugging log
            return jsonify({"error": "Invalid username or password"}), 401

        # Log the stored password hash and the provided password
        print(f"Stored password hash: {user.password_hash}")  # Debugging log
        print(f"Provided password: {data['password']}")  # Debugging log

        # Check the password
        if not check_password_hash(user.password_hash, data['password']):
            print("Password check failed")  # Debugging log
            return jsonify({"error": "Invalid username or password"}), 401

        # Log the user ID
        print(f"User ID: {user.id}")  # Debugging log

        # Generate a JWT token using the SECRET_KEY
        exp_time = datetime.utcnow() + timedelta(hours=24)
        payload = {"user_id": user.id, "exp": exp_time.timestamp()}  # Convert exp to timestamp
        print(f"JWT Payload: {payload}")  # Debugging log

        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm="HS256"
        )

        return jsonify({"message": "Login successful!", "token": token, "user_id": user.id}), 200
    except Exception as e:
        print(f"Error in login_user: {str(e)}")  # Debugging log
        return jsonify({"error": str(e)}), 500
    