import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == 'GET':
        user_id = session['user_id']
        stocks_dict = db.execute('SELECT DISTINCT symbol FROM transactions WHERE user_id = ?', user_id)
        stocks=[]
        prices=[]
        shares_list=[]
        names = []
        total_shares = []
        for s in stocks_dict:
            stocks.append(s['symbol'])
        for stock in stocks:
            if stock == 'NA':
                pass
            else:
                value = lookup(stock)
                prices.append(usd(value['price']))
                shares_buy = db.execute('SELECT SUM(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ? AND action = ?', user_id, stock, 'buy')
                shares_sell = db.execute('SELECT SUM(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ? AND action = ?', user_id, stock, 'Sell')
                shares = 0
                if str(shares_sell[0]['shares'])=='None':
                    shares = shares_buy[0]['shares']
                else:
                    shares = shares_buy[0]['shares'] - shares_sell[0]['shares']
                shares_list.append(shares)
                names.append(value['name'])
                total = value['price']*shares
                total_shares.append(usd(total))
        users_home_dict = db.execute('SELECT DISTINCT(user_id) FROM home')
        users_home = []
        symbol = []
        stocks_ = []
        for i in stocks:
                if i == 'NA':
                    pass
                else:
                    stocks_.append(i)
        for i in users_home_dict:
            users_home.append(i['user_id'])
        if user_id in users_home:
            symbol_dict = db.execute('SELECT symbol FROM home WHERE user_id = ?', user_id)
            for s in symbol_dict:
                    symbol.append(s['symbol'])
            difference = len(stocks_) - len(symbol)
            if difference!=0:
                for i in range(difference, len(stocks_)):
                    db.execute('INSERT INTO home (user_id, symbol, name, shares, price, total) VALUES (?, ?, ?, ?, ?, ?)', user_id, stocks_[i], names[i], shares_list[i], prices[i], total_shares[i])
            else:
                for i in range(0, len(stocks_)):
                    db.execute('UPDATE home SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?', shares_list[i], total_shares[i], user_id, stocks_[i])
        else:
            for i in range(0, len(stocks_)):
                db.execute('INSERT INTO home (user_id, symbol, name, shares, price, total) VALUES (?, ?, ?, ?, ?, ?)', user_id, stocks_[i], names[i], shares_list[i], prices[i], total_shares[i])
        index = db.execute('SELECT * FROM home WHERE user_id = ?', user_id)
        cash_dict = db.execute('SELECT cash FROM users WHERE id = ?', user_id)
        cash = usd(cash_dict[0]['cash'])
        return render_template('index.html', index=index, cash=cash)
    else:
        cash = int(request.form.get('cash'))
        user_id = session['user_id']
        if not cash:
            return apology('No amount was entered')
        if cash<0:
            return apology('Negative amount entered')
        existing_cash = db.execute('SELECT cash FROM users WHERE id = ?', user_id)
        total = cash + existing_cash[0]['cash']
        action = 'Add Cash'
        now = datetime.now()
        dateTime = now.strftime("%Y-%m-%d %H:%M:%S")
        db.execute('UPDATE users SET cash = ? WHERE id = ?', total, user_id)
        db.execute('INSERT INTO transactions (user_id, stock, symbol, action, price, shares, totalPrice, balance, dateTime) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)', user_id, 'NA', 'NA', action, cash, 0, cash, total, dateTime)
        return redirect('/')



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'GET':
        return render_template('buy.html')

    else:
        symbol = request.form.get('symbol')
        try:
            shares = int(request.form.get('shares'))
        except:
            return apology('enter an integer')

        if not symbol:
            return apology('No symbol was input')
        if not shares or shares<=0:
            return apology('Please enter 1 or more shares')
        user_id = session['user_id']
        cash = db.execute('SELECT cash FROM users WHERE id = ?', user_id)
        stock = lookup(symbol)
        if not stock:
            return apology('Invalid Symbol')
        price = stock['price']
        name = stock['name']
        total_price = price*int(shares)
        transactions = db.execute('SELECT * FROM transactions WHERE user_id = ?', user_id)
        if not transactions:
            balance = cash[0]['cash']
        else:
            balance = transactions[len(transactions)-1]['balance']
        balance = balance - total_price
        if balance<0:
            return apology('insufficient funds')
        action = 'buy'
        now = datetime.now()
        dateTime = now.strftime("%Y-%m-%d %H:%M:%S")
        db.execute('INSERT INTO transactions (user_id, stock, symbol, action, price, shares, totalPrice, balance, dateTime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', user_id, name, symbol, action, price, shares, total_price, balance, dateTime)
        #UPDATE table_name SET column1 = value1, column2 = value2, ...WHERE condition;
        db.execute('UPDATE users SET cash = ? WHERE id = ?', balance, user_id)
        #INSERT INTO table_name (column1, column2, column3, ...)VALUES (value1, value2, value3, ...);
        return redirect('/')



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session['user_id']
    transactions = db.execute('SELECT * FROM transactions WHERE user_id = ?', user_id)
    if not transactions:
        return apology('No History of Transactions', 404)
    else:
        for transaction in transactions:
            if transaction['action'] == 'Sell':
                transaction['shares'] = f'-{transaction["shares"]}'
        return render_template('history.html', transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == 'GET':
        return render_template('quote.html')
    else:
        symbol = request.form.get('symbol')
        if not symbol:
            return apology('No Symbol was entered')
        value = lookup(symbol)
        dollar = usd(value['price'])
        paragraph = f'A share of {value["name"]} ({value["symbol"]}) costs {dollar}.'
        if not value:
            return apology('Incorrect Symbol/No matching Symbol was found')
        return render_template('quoted.html', value=paragraph)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'GET':
        return render_template('register.html')
    else:
        name = request.form.get('username')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')
        if not name:
            return apology('No Username was entered')
        if not password:
            return apology('No Password was entered')
        if confirmation != password:
            return apology('The password and confirmation did not match')
        hash = generate_password_hash(password)
        try:
            db.execute('INSERT INTO users (username,hash) VALUES (?,?)', name, hash)
        except:
            return apology('Username already exists')

        session_ = db.execute('SELECT id FROM users WHERE username = ?', name)
        session['user_id'] = session_[0]['id']

        return redirect('/')




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session['user_id']
    symbols = []
    symbol_dict = db.execute('SELECT symbol FROM home WHERE user_id = ?', user_id)
    for s in symbol_dict:
        symbols.append(s['symbol'])
    if request.method == 'GET':
        return render_template('sell.html', symbols=symbols)
    else:
        symbol_user = request.form.get('symbol')
        if not symbol_user:
            return apology('No symbol was input')
        if symbol_user in symbols:
            pass
        else:
            return apology('You do not own any shares of this symbol')
        shares_owned_dict = db.execute('SELECT shares FROM home WHERE symbol = ? AND user_id = ?', symbol_user, user_id)
        shares_owned = shares_owned_dict[0]['shares']
        shares_user = int(request.form.get('shares'))
        if shares_user > shares_owned:
            return apology(f'You do not own {shares_user} shares')
        if shares_user < 0:
            return apology('You have entered negative shares')
        value = lookup(symbol_user)
        stock = value['name']
        price = value['price']
        total_price = price * shares_user
        cash_dict = db.execute('SELECT cash FROM users WHERE id = ?', user_id)
        cash = cash_dict[0]['cash']
        balance = cash + total_price
        action = 'Sell'
        remaining_shares = shares_owned - shares_user
        remaining_price = remaining_shares * price
        now = datetime.now()
        dateTime = now.strftime("%Y-%m-%d %H:%M:%S")
        db.execute('INSERT INTO transactions (user_id, stock, symbol, action, price, shares, totalPrice, balance, dateTime) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)', user_id, stock, symbol_user, action, price, shares_user, total_price, balance, dateTime)
        db.execute('UPDATE home SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?', remaining_shares, remaining_price, user_id, symbol_user)
        db.execute('UPDATE users SET cash = ? WHERE id = ?', balance, user_id)
        return redirect('/')
