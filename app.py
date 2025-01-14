import sqlite3
from flask import Flask, render_template, request, redirect, session
import threading
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# Thread-local storage for database connections
thread_local = threading.local()


# Set a secret key for sessions (keep it secret!)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

# Session configuration
app.config["SESSION_PERMANENT"] = True
app.permanent_session_lifetime = timedelta(minutes=4320)

# Store sessions on the filesystem for security
app.config["SESSION_TYPE"] = "filesystem"  

MOVIES = [
    "Black Panther",
    "Dangerous Lies",
    "Avengers Endgame",
    "Joker",
    "Ford v Ferrari",
    "Fast & Furious Presents: Hobbs & Shaw",
    "Charlie's Angels",
    "Escape Room",
    "The Outpost",
    "Furiosa: A Mad Max Saga",
    "Neema"
]

def get_connection():
    # Check if the current thread already has a connection
    if not hasattr(thread_local, "db"):

        # Add check_same_thread=False to allow connection sharing across threads
        thread_local.db = sqlite3.connect("movies.db", check_same_thread=False)
        thread_local.db.row_factory = sqlite3.Row  # Optional: allows accessing rows as dictionaries
    return thread_local.db

def save_user_cart(cart, username):
    if not username:
        return render_template("error.html", message="Username cannot be None when saving cart.")
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes=4320)

    # Using context manager to ensure the connection is properly closed after use
    with  get_connection() as conn:
        conn.execute("INSERT INTO temp_carts (user_name, cart_data, expiration_time) VALUES (?, ?, ?)", (username, str(cart), expiration_time))
        conn.commit()

def get_saved_cart_for_user(username):
    
    # Retrieve the cart from temp storage based on username (or another identifier)
    with get_connection() as conn:
        cart_data = conn.execute("SELECT cart_data FROM temp_carts WHERE expiration_time > ? AND user_name = ?",
                             (datetime.now(timezone.utc), username)).fetchone()
    
    if cart_data:
        return eval(cart_data["cart_data"])  # Convert string back to list
    return None


@app.route("/")
def index():
    
    # If the 'name' session variable doesn't exist, redirect to login
    if "name" not in session:
        return redirect("/login")
    print(session["name"])  # This will print the name to the console
    return render_template("/index.html", movies=MOVIES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")

        # Check for a saved cart in temporary storage
        cart = get_saved_cart_for_user(username)

        session["name"] = username

        session["cart"] = cart or []  # Use saved cart if available
        # Redirect to the home page after successful login
        return redirect("/")
    # Render login form if the method is GET
    return render_template("login.html")


@app.route("/submit", methods=["POST"])
def subit():
    # Check if the user is logged in before allowing form submission
    if "name" not in session:
        # Redirect to login if not logged in
        return redirect("/login")  
    
    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")
    moviename = request.form.get("moviename")
    actorname = request.form.get("actorname")
    comment = request.form.get("comment")
    
    if not firstname or not lastname or not moviename or not actorname or not comment:
        return render_template("error.html", message="Kindly provide all the details.")
    
    elif moviename not in MOVIES:
        return render_template("/error.html", message="Invalid movie name.")

    # Insert data to database
    with get_connection() as conn:
        conn.execute("INSERT INTO movies (first_name, last_name, movie_name, actor_name, comment) VALUES (?, ?, ?, ?, ?)",
                 (firstname, lastname, moviename, actorname, comment))
        conn.commit()    
    return redirect("/submitted")


@app.route("/submitted")
def submitted():
    with get_connection() as conn:
        movies = conn.execute("SELECT * FROM movies").fetchall()
    return render_template("submitted.html", movies=movies)

@app.route("/movies")
def movies():
    with get_connection() as conn:
        movies = conn.execute("SELECT * FROM store").fetchall()
    return render_template("movies.html", movies=movies)
        
@app.route("/cart", methods=["GET", "POST"])
def cart():
    # Check whether the art exists
    if "cart" not in session:
        session["cart"] = []

    # Post data to server
    if request.method == "POST":
        movieid = request.form.get("id")
        if movieid and movieid not in session["cart"]:
            session["cart"].append(movieid)
        session.modified = True  # Ensure session changes are saved
        return redirect("/cart")
    
    # Get data from server to show items on cart
    with get_connection() as conn:

        # Dynamically create placeholders for the SQL query
        placeholders = ",".join(["?"] * len(session["cart"])) if session["cart"] else "NULL"

        # Fetch data for stores in the cart
        query = f"SELECT * FROM store WHERE id IN ({placeholders})"
        stores = conn.execute(query, session["cart"]).fetchall()
    return render_template("cart.html", stores=stores)


@app.route("/logout")
def logout():
    # Ensure the cart is saved before logging out
    user_cart = session.get("cart", [])

    # Retrieve the username from the session
    user_name = session.get("name") 
    # Save the cart to and username temporary storage (e.g., a database or a cache) for 10 minutes
    if user_cart and user_name:
        save_user_cart(user_cart, user_name)
        
    # Remove the 'name' session variable to log the user out if it exists
    session.clear() 
    # Redirect to the login page after logging out
    return redirect("/login")

if __name__ == '__main__':
    app.run(debug=True)