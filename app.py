import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    # get users cash
    cash = db.execute("SELECT cash FROM users WHERE id =?", user_id)[0]["cash"]

    # get users holdings
    rows = db.execute("""
            SELECT symbol, SUM(shares) AS total_shares
            FROM transactions
            WHERE user_id = ?
            GROUP BY symbol
            HAVING total_shares > 0""", user_id)

    # build portfolio list with current prices
    portfolio = []
    total_value = cash

    for row in rows:
        stock = lookup(row["symbol"])
        price = stock["price"]
        shares = row["total_shares"]
        value = shares * price
        portfolio.append({
            "symbol": row["symbol"],
            "name": stock["name"],
            "shares": shares,
            "price": price,
            "value": value
        })
        total_value += value
    return render_template("index.html", portfolio=portfolio, cash=cash, total_value=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    user_id = session["user_id"]

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate inputs
        if not symbol:
            return apology("must provide symbol", 400)
        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("invalid shares", 400)

        shares = int(shares)

        # Look up stock
        stock = lookup(symbol)
        if stock is None:
            return apology("invalid symbol", 400)

        price = stock["price"]
        cost = shares * price

        # Check user's cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        if cost > cash:
            return apology("not enough cash", 403)

        # Deduct cash
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, user_id)

        # Record transaction (positive shares for buy)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                   user_id, symbol, shares, price)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transactions = db.execute("""
                            SELECT symbol, shares, price, transacted
                            FROM transactions
                            WHERE user_id = ?
                            ORDER BY transacted DESC
                            """, user_id)

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Validate symbol
        if not symbol:
            return apology("must provide symbol", 400)

        stock = lookup(symbol.upper())
        if stock is None:
            return apology("invalid symbol", 400)

        # Pass stock info to template
        return render_template("quoted.html", stock=stock)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        if not password:
            return apology("must provide password", 400)
        if password != confirmation:
            return apology("password do not match", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        if len(rows) != 0:
            return apology("username already exists", 400)

        hash_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_pw)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # validate input
        if not symbol:
            return apology("must provide symbol", 400)
        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("invalid number of shares", 400)

        shares = int(shares)

        (shares)

        # Check how many shares the user owns (from transactions table)
        owned = db.execute(
            "SELECT SUM(shares) AS total FROM transactions WHERE user_id = ? AND symbol = ?",
            user_id, symbol
        )[0]["total"]

        if owned is None or shares > owned:
            return apology("not enough shares", 400)

        # Look up current stock price
        stock = lookup(symbol)
        if stock is None:
            return apology("invalid symbol", 400)

        price = stock["price"]
        proceeds = shares * price

        # Update user's cash
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", proceeds, user_id)

        # Record transaction (negative shares for sell)
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
            user_id, symbol, -shares, price
        )

        return redirect("/")

    else:
        # Show dropdown of stocks user owns (query transactions, not portfolio)
        stocks = db.execute("""
            SELECT symbol, SUM(shares) AS total
            FROM transactions
            WHERE user_id = ?
            GROUP BY symbol
            HAVING total > 0
        """, user_id)

        return render_template("sell.html", stocks=stocks)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Allow user to add cash"""
    if request.method == "POST":
        amount = request.form.get("amount")
        if not amount or float(amount) <= 0:
            return apology("must provide positive amount", 403)

        user_id = session["user_id"]
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", float(amount), user_id)
        flash("cash added successfully")
        return redirect("/")
    else:
        return render_template("add_cash.html")
