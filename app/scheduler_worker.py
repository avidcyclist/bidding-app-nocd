
"""

import sys
import os


# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)


from flask import Flask
from app import db
from app.models import Listing, User, Notification, Bid
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from app.utils import send_sms
from config import Config
import logging

# Function to check for expired listings
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to check for expired listings
def check_expired_listings():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    db.init_app(app)

    with app.app_context():
        now = datetime.utcnow()
        logger.info(f"Running check_expired_listings at {now}")
        expired_listings = Listing.query.filter(Listing.end_time <= now, Listing.is_active == True).all()
        logger.info(f"Found {len(expired_listings)} expired listings")
        for listing in expired_listings:
            logger.info(f"Marking listing {listing.id} as inactive")
            listing.is_active = False
            db.session.commit()

            # Notify the seller
            seller = User.query.get(listing.user_id)
            if seller:
                logger.info(f"Notifying seller {seller.id} about listing {listing.id}")
                send_sms(seller.phone_number, f"Your listing '{listing.title}' has ended.")
                seller_notification = Notification(
                    user_id=listing.user_id,
                    message=f"Your listing '{listing.title}' has ended.",
                    is_read=False
                )
                db.session.add(seller_notification)

            # Notify the highest bidder
            highest_bid = Bid.query.filter_by(listing_id=listing.id).order_by(Bid.amount.desc()).first()
            if highest_bid:
                logger.info(f"Notifying winner {highest_bid.user_id} about listing {listing.id}")
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

# Initialize the scheduler
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_expired_listings, trigger="interval", minutes=1)
    logger.info("Scheduler started")
    scheduler.start()

    # Keep the script running
    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        
        """