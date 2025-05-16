from app import db

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)  # Optional for text messaging
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Equivalent Raw SQL:
    # CREATE TABLE users (
    #     id INT AUTO_INCREMENT PRIMARY KEY,
    #     username VARCHAR(80) NOT NULL UNIQUE,
    #     email VARCHAR(120) NOT NULL UNIQUE,
    #     password_hash VARCHAR(128) NOT NULL,
    #     phone_number VARCHAR(15) NOT NULL,
    #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    # );

# Listing Model
class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    starting_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)  # To mark if the listing is active or not

    # Equivalent Raw SQL:
    # CREATE TABLE listings (
    #     id INT AUTO_INCREMENT PRIMARY KEY,
    #     title VARCHAR(200) NOT NULL,
    #     description TEXT NOT NULL,
    #     starting_price FLOAT NOT NULL,
    #     current_price FLOAT NOT NULL,
    #     end_time DATETIME NOT NULL,
    #     image_url VARCHAR(255),
    #     user_id INT NOT NULL,
    #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #     FOREIGN KEY (user_id) REFERENCES users(id)
    # );

# Bid Model
class Bid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    # Equivalent Raw SQL:
    # CREATE TABLE bids (
    #     id INT AUTO_INCREMENT PRIMARY KEY,
    #     amount FLOAT NOT NULL,
    #     user_id INT NOT NULL,
    #     listing_id INT NOT NULL,
    #     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #     FOREIGN KEY (user_id) REFERENCES users(id),
    #     FOREIGN KEY (listing_id) REFERENCES listings(id)
    # );

# Notification Model
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Equivalent Raw SQL:
    # CREATE TABLE notifications (
    #     id INT AUTO_INCREMENT PRIMARY KEY,
    #     user_id INT NOT NULL,
    #     message VARCHAR(255) NOT NULL,
    #     is_read BOOLEAN DEFAULT FALSE,
    #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #     FOREIGN KEY (user_id) REFERENCES users(id)
    # );