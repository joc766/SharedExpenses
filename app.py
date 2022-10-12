#TODO look up how to get the form that was submitted separately. 
# also see how to make html that adds inputs for each person's name to be added to the group

#TODO make the add expense page

# save this as app.py
from flask import Flask, render_template, request, session, redirect, flash, jsonify
from tempfile import mkdtemp
from database import *
from database import total_unpaid
from flask_session import Session
from helpers import apology, login_required

from werkzeug.security import check_password_hash, generate_password_hash

FLASK_ENV = 'development'
app = Flask(__name__)
db_file = r"Expenses.db"

#TODO password hash

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config['TESTING'] = True
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/", methods=["GET", "POST"])
@login_required
def main_page():
    if request.method == "GET":
        conn = create_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT Debt FROM Users WHERE Venmo = \"{}\";".format(session["user_id"]))
        debt = cursor.fetchone()[0]
        users_debt = {}
        cursor.execute("SELECT DISTINCT Venmo FROM Users WHERE groupID IN (SELECT groupID FROM Users WHERE Venmo=\
            \"{user_venmo}\");".format(user_venmo=session["user_id"]))
        groupees = cursor.fetchall()
        for groupee in groupees:
            users_debt[groupee[0]] = get_user_debt(conn, session["user_id"], groupee[0])
        return render_template("main_page.html", user=session["user_id"], owed=debt, users_debt=users_debt)
    if request.method == "POST":
        print("HERE")
        conn = create_connection(db_file)
        cursor = conn.cursor()
        user_venmo = session["user_id"]
        debtor_venmo = request.form.get("debtor")
        print("HERE IT IS {}".format(debtor_venmo))
        cost = float(request.form.get("cost"))
        cursor.execute("SELECT Name FROM Users WHERE Venmo = \"{}\";".format(debtor_venmo))
        debtor_name = cursor.fetchone()[0]
        cursor.execute("SELECT Debt FROM Users WHERE Venmo = \"{}\";".format(user_venmo))
        old_debt = float(cursor.fetchone()[0])
        new_debt = old_debt - cost
        cursor.execute("UPDATE Dues SET Paid = True WHERE venmo = \"{venmo}\" AND expenseID IN \
            (SELECT id FROM Expenses WHERE Who_paid = \"{debtor}\");".format(venmo=user_venmo, debtor=debtor_name))
        cursor.execute("UPDATE Users SET Debt = {} WHERE Venmo = \"{}\";".format(new_debt, user_venmo))
        conn.commit()
        conn.close()
        return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    """ Log user in """
    # Forget any user_id 
    #session.clear()
    conn = create_connection(db_file)
    cursor = conn.cursor()
    if request.method == "POST":

        username = request.form.get("venmo")
        # Ensure username was submitted
        if not username:
            cursor.close()
            return apology("must provide venmo username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            cursor.close()
            return apology("must provide password", 403)

        # Query database for username
        cursor.execute("SELECT Hash FROM Users WHERE Venmo = \"{}\" AND Hash IS NOT NULL;".format(request.form.get("venmo")))
        pwdhash = cursor.fetchone()[0]

        # Ensure username exists and password is correct
        if not check_password_hash(pwdhash, request.form.get("password")):
            cursor.close()
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = username

        # Redirect user to home page
        cursor.close()
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register(new_group = False):
    """Register user"""
    conn = create_connection(db_file)
    cursor = conn.cursor()
    if request.method == "GET":
        return render_template("register.html")
    else:
        pword = request.form.get("password")
        pconfirm = request.form.get("password_confirm")
        if (pword == pconfirm):
            name = request.form.get("name")
            venmo = request.form.get("venmo")
            group_no = request.form.get("group_no")
            hash = generate_password_hash(pword)
            cursor.execute("INSERT INTO Users (Name, Debt, Venmo, groupID, Hash) VALUES (\"{}\", {}, \"{}\", {}, \"{}\");".format(name, 0, venmo, group_no, hash))
            conn.commit()
            conn.close()
            return redirect('/login')
        else:
            return apology("password and confirmation do not match")

@app.route("/register_group", methods=["GET", "POST"])
def register_group():
    conn = create_connection(db_file)
    cursor = conn.cursor()
    group_name = request.form.get("group_name")
    cursor.execute("INSERT INTO Groups (Group_name) VALUES (\"{}\");".format(group_name))
    conn.commit()
    cursor.execute("SELECT id FROM Groups WHERE Group_name = \"{}\";".format(group_name))
    group_no = cursor.fetchone()[0]
    conn.close()
    return render_template("New_Group.html", group_no = group_no)

@app.route("/Dues", methods=["GET", "POST"]) #Going to change this to '/user/<username>' later so that you can render a certain person's page
@login_required
def user():
    if request.method == "GET":
        conn = create_connection(db_file)
        ids = get_groups(conn, session["user_id"])
        groups = []
        for id in ids:
            groups.append(group_id_to_name(conn, id))
        length = len(groups)
        conn.close()
        return render_template("personal_dues.html", groups=groups, ids=ids, length=length)
    if request.method == "POST":
        group = request.form.get("groupID")
        print("Got here")
        return redirect('/Dues/{}'.format(group))


@app.route("/Dues/<group>", methods=["GET", "POST"])
@login_required
def personal_dues(group):
    conn = create_connection(db_file)
    if request.method=="GET":
        dues = get_all_unpaid(conn, session["user_id"], group) # change this to work for all of them just like previous pages
        #TODO list out the options for each user with POST method and buttons
        conn.close()
        return render_template('dues.html', dues=dues, group=group)
    if request.method=="POST":
        expenseID = request.form.get("expenseID")
        pay_due(conn, session["user_id"], expenseID)
        dues = get_all_unpaid(conn, session["user_id"], group)
        #TODO same as previous
        conn.close()
        return render_template('dues.html', dues=dues, group=group)


@app.route('/Archive/<group>', methods=["GET", "POST"])
def group_archive(group):
    conn = create_connection(db_file)
    if request.method=="GET":
        dues = get_all_paid(conn, session["user_id"], group)
        #TODO list out the options for each user with POST method and buttons
        conn.close()
        return render_template('group_archive.html', dues=dues, group=group)
    if request.method=="POST":
        expenseID = request.form.get("expenseID")
        unpay_due(conn, session["user_id"], expenseID)
        dues = get_all_paid(conn, session["user_id"], group)
        #TODO same as previous
        conn.close()
        return render_template('group_archive.html', dues=dues, group=group)


@app.route("/Archive", methods=["GET", "POST"]) #Going to change this to '/user/<username>' later so that you can render a certain person's page
@login_required
def archive():
    conn = create_connection(db_file)
    if request.method == 'GET':
        conn = create_connection(db_file)
        print(session["user_id"])
        ids = get_groups(conn, session["user_id"])
        groups = []
        for id in ids:
            groups.append(group_id_to_name(conn, id))
        length = len(groups)
        conn.close()
        return render_template("archive.html", ids=ids, groups=groups, length=length)
    if request.method=="POST":
        group = request.form.get("groupID")
        conn.close()
        return redirect('/Archive/{}'.format(group))

@app.route('/AllExpenses', methods=['GET', 'POST'])
@login_required
def all_expenses():
    if request.method == 'GET':
        conn = create_connection(db_file)
        ids = get_groups(conn, session["user_id"])
        groups = []
        for id in ids:
            groups.append(group_id_to_name(conn, id))
        length = len(groups)
        conn.close()
        return render_template("all_expenses.html", ids=ids, groups=groups, length=length)
    if request.method == 'POST':
        conn = create_connection(db_file)
        groupID = int(request.form.get("groupID"))
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Expenses WHERE groupID = {};".format(groupID))
        expenses = cursor.fetchall()
        all_info = []
        for expense in expenses:
            id = expense[0]
            row = get_expense_info(conn, id)
            all_info.append(row)

        ids = get_users(conn, groupID)
        users = []
        for id in ids:
            users.append(id_to_name(conn, id))
        conn.close()
        return render_template("display_expenses.html", users=users, all_info=all_info)

@app.route('/NewExpense', methods=['GET', 'POST'])
@login_required
def new_due():
    if request.method == 'GET':
        conn = create_connection(db_file)
        ids = get_groups(conn, session["user_id"])
        groups = []
        for id in ids:
            groups.append(group_id_to_name(conn, id))
        length = len(groups)
        users = []
        conn.close()
        return render_template("new_expense.html", ids_groups=zip(ids, groups), length=length)
    if request.method == "POST":
        conn = create_connection(db_file)
        cursor = conn.cursor()

        shares = {}
        # get the group ID from the choice of which button was selected
        groupID = int(request.form.get("groupID"))
        print("Group id = {}".format(groupID))
        # get the amount that was submitted
        amount = int(request.form.get("amount"))
        # get the description that was submitted
        description = request.form.get("description")
        # get who paid from submission
        cursor.execute("SELECT Name FROM Users WHERE Venmo = \"{}\";".format(session["user_id"]))
        who_paid = cursor.fetchone()[0]
        users = get_users(conn, groupID)
        for user in users:
            name = id_to_name(conn, user)
            shares[name] = 1
        add_new_expense(conn, groupID, amount, description, who_paid, shares)
        conn.close()
        return redirect('/NewExpense')

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    
@app.route('/shutdown', methods=['GET'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'