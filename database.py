#TODO Make a feature that shows who you owe and how much (possibly including cancellations)

#TODO should finish updating to store the venmo as who_paid and not a name
""" Usable python functions to create and manipulate the Shared Expenses database created
in SQLite3. 

Functions:

    create_connection(db_file) -> Connection (use for all actions)
    create_new_database(db_file, users, venmos) -> Connection (unique use for testing)
    add_new_expense(conn, amount, description, who_paid, shares) -> None (use when submitting expense)
    read_spreadsheet(conn, file) -> None (unique use for testing)
    pay_due(conn, userID, expenseID) -> None (use when paying expense)
    pay_person(conn, debtorID, userID) -> None (use when paying expenses)
    name_to_id(conn, name) -> int (helper function)
    id_to_name(conn, id) -> str (helper function)
    get_all_unpaid(conn, userID, groupID) -> list (use for listing unpaid expenses on Dues page)
    get_users(conn, groupID) -> list (mostly a helper function)
    get_password(conn, userID) -> str (use for login page)
    get_groups(conn, venmo) -> list
    has_registered(conn, venmo) -> bool

"""
import sqlite3
from sqlite3 import Error
from datetime import date
import csv
from flask import render_template
total_unpaid = 0


def create_connection(db_file: str):
    """ Creates a connection to the SQLite database.
        
        Returns the connection to the database for future use. Does not
        Create the cursor; user must do this themselves.

        If the path specified in db_file does not exist, a file will be
        created in the specified location.

        Parameters
        ----------
        db_file: str
            Path to database file that will be opened

        Return
        ------
        conn : Connection
            Connection to the SQLite database

    """
    conn = None
    try: 
        conn = sqlite3.connect(db_file)
        print(sqlite3.version)
        return conn
    except Error as e:
        print(e)

def create_new_database(db_file: str):
    """ Creates a new database for Shared Expenses with the tables Users
    Expenses and Dues. 

    Parameters
    ----------
    db_file : str
        Path to database file that will be created

    Returns
    -------
    conn : Connection
        The connection the to SQLite database

    """
    conn = create_connection(db_file)
    cursor = conn.cursor()


    try:
        cursor.execute("CREATE TABLE Groups (\
            id INTEGER NOT NULL PRIMARY KEY,\
            Group_name varchar(30) NOT NULL\
            );")
        # Create the Users table
        cursor.execute("CREATE TABLE Users (\
            id INTEGER NOT NULL PRIMARY KEY,\
            Name varchar(20),\
            Username varchar(20) UNIQUE,\
            Debt DOUBLE(7,2),\
            Venmo varchar(30), \
            groupID INTEGER NOT NULL,\
            Hash TEXT,\
            FOREIGN KEY(groupID) REFERENCES Groups(id)\
            );")
            # Change Who_paid to id INT?: YES
        cursor.execute("CREATE TABLE Expenses (\
            id INTEGER NOT NULL PRIMARY KEY,\
            Amount DOUBLE(7,2),\
            Expense_name TEXT,\
            Who_paid varchar(20),\
            Num_shares INTEGER,\
            Person_cost DOUBLE(7,2),\
            Date DATE,\
            groupID INT NOT NULL,\
            FOREIGN KEY(groupID) REFERENCES Groups(id),\
            FOREIGN KEY(Who_paid) REFERENCES Users(id)\
            );")
        cursor.execute("CREATE TABLE Dues (\
            venmo TEXT NOT NULL,\
            expenseID INTEGER NOT NULL,\
            Shares DOUBLE(7,2) NOT NULL,\
            Paid BOOLEAN NOT NULL,\
            groupID INT NOT NULL,\
            FOREIGN KEY(groupID) REFERENCES Groups(id)\
            FOREIGN KEY(expenseID) REFERENCES Expenses(id)\
            );")
        cursor.close()
        return conn
    except Error as e:
        print(e)
        return

def initialize_group(conn, Group_name, users, venmos):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Groups (Group_name) VALUES (\"{}\");".format(Group_name))
    conn.commit()
    cursor.execute("SELECT id FROM Groups;".format(Group_name))
    groupID = cursor.fetchall()[-1][0]
    for (user, venmo) in zip(users, venmos):
        try:
            cursor.execute("INSERT INTO Users (Name, Debt, Venmo, groupID) VALUES (\"{0}\", 0.00, \"{1}\", \"{2}\");".format(user, venmo, groupID))
            conn.commit()
        except Error as e:
            print(e)
            return
    cursor.close()

def get_user_debt(conn, user_venmo, debtor_venmo):
    cursor = conn.cursor()
    print(debtor_venmo)
    cursor.execute("SELECT Name FROM Users WHERE Venmo = \"{}\";".format(debtor_venmo))
    debtor_name = cursor.fetchone()[0]
    cursor.execute("SELECT id, Person_cost FROM Expenses WHERE id IN (SELECT expenseID FROM Dues WHERE venmo = \"{user}\" \
    AND Paid = False AND expenseID IN (SELECT id FROM Expenses WHERE Who_paid = \"{debtor}\"));".format\
    (user=user_venmo, debtor=debtor_name))

    total_debt = 0
    all_costs = cursor.fetchall()
    for cost in all_costs:
        id = cost[0]
        person_cost = cost[1]
        cursor.execute("SELECT Shares FROM Dues WHERE expenseID = {} AND venmo = \"{}\";".format(id, user_venmo))
        shares = cursor.fetchone()[0]
        total_debt += person_cost * shares

    cursor.close()
    return total_debt
    

def add_new_expense(conn, groupID, amount, description, who_paid, shares: dict): 
    """ Adds a new expense to the Expenses table.

    Ex. If 4 people are sharing an expense evenly, each of the 4 people gets 1 share
    and any others get 0. Each person then pays 1/4 the total amount of the expense.


    Parameters
    ----------
        group : int
            id of the group being used
        conn : Connection
            Connection to the SQLite database
        amount : float
            The total cost of the expense
        description : str
            Description of what the expense was for
        who_paid : str
            Name of person who paid
        shares : dict
            List that assigns a share to each person for the expense. Typically 1 if 
            the cost of an item is to be shared evenly across all contributors. 
            
    """
    today = date.today()
    # NEED TO INCLUDE ERRORS FOR INVALID INPUTS AND SHIT


    # Sum all of the shares in the dictionary shares to get the Num_shares value
    keys = shares.keys()
    total_shares = 0
    for key in keys:
        total_shares += shares[key]
    
    # Calculate the per person cost of each expense
    person_cost = amount / total_shares
    # Create the SQLite query
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Expenses (Amount, Expense_name, Who_paid, Num_Shares, Person_cost, Date, groupID)\
                    VALUES ({}, \"{}\", \"{}\", {}, {}, \"{}\", {});".format(amount, description, who_paid, total_shares, person_cost, today, groupID))
    conn.commit()

    cursor.execute("SELECT id FROM Expenses")
    expenseID = cursor.fetchall()[-1][0]
    # Execute SQL Query on Dues table for each person
    for key in keys:
        if (shares[key] > 0):
            has_paid = False
            if (key == who_paid):
                has_paid = True
            cursor.execute("SELECT Venmo FROM Users WHERE Name=\"{}\" AND groupID=\"{}\";".format(key, groupID))
            venmo = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Dues (venmo, expenseID, Shares, Paid, groupID)\
                VAlUES (\"{}\", {}, {}, {}, {});".format(venmo, expenseID, shares[key], has_paid, groupID))
            cursor.execute("SELECT Debt FROM Users WHERE Venmo = \"{}\";".format(venmo))
            if key != who_paid:
                prev_debt = cursor.fetchone()[0]
                new_debt = prev_debt + person_cost * shares[key]
                cursor.execute("UPDATE Users SET Debt = {} WHERE Venmo = \"{}\";".format(new_debt, venmo))
            conn.commit()
    cursor.close()

def read_spreadsheet(conn, file, groupID):
    """ Reads information from Shared Expenses spreadsheet previously used in Austin House Shared Expenses
    Google Sheet into the new SQLite Database.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    file : str
        Path to csv file to be read into database

    """
    names_in_order = ["Jack", "Joe", "Tobin", "Marcus", "Nathan", "Ben", "Connor", "JP", "Jami"]
    with open(file) as csv_file:
        reader = csv.reader(csv_file)
        shares = {}
        for row in reader:
            description = row[0]
            amount = float(row[1][1:])
            who_paid = row[12]
            for i in range(2, 11):
                shares[names_in_order[i-2]] = float(row[i])
            add_new_expense(conn, groupID, amount, description, who_paid, shares)
    csv_file.close()

def pay_due(conn, venmo: str, expenseID: int):
    """ Pays a specific due in Dues.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    userID : int
        Unique id of the person paying a debt
    expenseID : int
        Unique id of the expense being payed

    """
    cursor = conn.cursor()
    cursor.execute("UPDATE Dues SET Paid = True WHERE Venmo = \"{}\" AND expenseID = {};".format(venmo, expenseID))
    cursor.execute("SELECT Person_cost FROM Expenses WHERE id = {};".format(expenseID))
    person_cost = cursor.fetchone()[0]
    cursor.execute("SELECT Shares FROM Dues WHERE Venmo = \"{}\" AND expenseID = {};".format(venmo, expenseID))
    shares = cursor.fetchone()[0]
    cursor.execute("SELECT Debt FROM Users WHERE Venmo = \"{}\";".format(venmo))
    prev_debt = cursor.fetchone()[0]
    new_debt = prev_debt - person_cost * shares
    cursor.execute("UPDATE Users SET Debt = {} WHERE Venmo = \"{}\"".format(new_debt, venmo))
    conn.commit()
    cursor.close()

def unpay_due(conn, venmo: str, expenseID: int):
    """ Pays a specific due in Dues.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    userID : int
        Unique id of the person paying a debt
    expenseID : int
        Unique id of the expense being payed

    """
    cursor = conn.cursor()
    cursor.execute("UPDATE Dues SET Paid = False WHERE Venmo = \"{}\" AND expenseID = {};".format(venmo, expenseID))
    cursor.execute("SELECT Person_cost FROM Expenses WHERE id = {};".format(expenseID))
    person_cost = cursor.fetchone()[0]
    cursor.execute("SELECT Shares FROM Dues WHERE Venmo = \"{}\" AND expenseID = {};".format(venmo, expenseID))
    shares = cursor.fetchone()[0]
    cursor.execute("SELECT Debt FROM Users WHERE Venmo = \"{}\";".format(venmo))
    prev_debt = cursor.fetchone()[0]
    new_debt = prev_debt + person_cost * shares
    cursor.execute("UPDATE Users SET Debt = {} WHERE Venmo = \"{}\"".format(new_debt, venmo))
    conn.commit()
    cursor.close

def pay_person(conn, debtorID: int, userID: int):
    """ Pays all of the unpaid expenses due to a given person.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    debtorID : int
        Unique id of the person who is owed
    userID : int
        Unique id of the person who is paying their debt

    """
    cursor = conn.cursor()

    # Get the Name for the userID
    cursor.execute("SELECT Name FROM Users WHERE id = {}".format(debtorID))
    name = cursor.fetchone()[0]

    # Find all of the expense IDs 
    cursor.execute("SELECT id FROM Expenses WHERE who_paid = \"{}\"".format(name))
    unpaid = cursor.fetchall()

    # Pay each of the expense IDs
    for row in unpaid:
        expenseID = row[0]
        pay_due(conn, userID, expenseID)
    cursor.close()

def name_to_id(conn, name: str):
    """ Converts a name to an id.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    name : str
        Username

    Returns
    -------
    id : int
        Unique id connected to username
    
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users WHERE Name = \"{}\";".format(name))
    id = cursor.fetchone()[0]
    cursor.close()
    return id

def id_to_name(conn, id: int):
    """ Converts an id to a name.

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    id : int
        Unique primary key id

    Returns
    -------
    name : str
        Unique username connected to id
    
    """
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM Users WHERE id = {};".format(id))
    name = cursor.fetchone()[0]
    cursor.close()
    return name

def get_all_unpaid(conn, venmo, groupID):
    """ Gets all of the unpaid dues that a user has

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    name : str
        Person whose list of debts will be returned
    
    Returns
    -------
    all_display_info : list
        2d array where each row contains date, cost, description, and venmo of person who
        is owed for an unpaid due. 

    """
    # When displaying the price information, use the "%.2f" placeholder so that it rounds to the nearest cent
    cursor = conn.cursor()
    cursor.execute("SELECT id, Date, Person_cost, Shares, Expense_name, Who_paid\
         FROM Dues INNER JOIN Expenses ON Dues.expenseID=Expenses.id WHERE venmo=\"{venmo}\" AND Paid = False \
             AND Expenses.groupID = {groupID};".format(venmo=venmo, groupID=groupID))
    unpaid_dues = cursor.fetchall()
    all_display_info = []
    total_unpaid = 0

    for due in unpaid_dues:
        expenseID = int(due[0])
        date = str(due[1])
        person_cost = float(due[2])
        num_shares = float(due[3])
        cost = person_cost * num_shares
        description = str(due[4])
        who_paid = str(due[5])
        total_unpaid += person_cost * num_shares

        cursor.execute("SELECT Venmo FROM Users WHERE Name = \"{}\";".format(who_paid))
        venmo = str(cursor.fetchone()[0])

        cost = person_cost * num_shares
        display_row = []
        display_row.append(date)
        display_row.append(cost)
        display_row.append(description)
        display_row.append(venmo)
        display_row.append(expenseID)
        all_display_info.append(display_row)

    cursor.close()
    return all_display_info

def get_all_paid(conn, venmo, groupID):
    """ Gets all of the paid dues that a user has

    Parameters
    ----------
    conn : Connection
        Connection to the SQLite database
    name : str
        Person whose list of debts will be returned
    
    Returns
    -------
    all_display_info : list
        2d array where each row contains date, cost, description, and venmo of person who
        is owed for an unpaid due. 

    """
    # When displaying the price information, use the ".2f" placeholder so that it rounds to the nearest cent
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Dues WHERE venmo = \"{}\" AND Paid = True AND groupID = {};".format(venmo, groupID))
    unpaid_dues = cursor.fetchall()
    all_display_info = []
    total_paid = 0

    for due in unpaid_dues:
        expenseID = due[1]
        num_shares = due[2]
        cursor.execute("SELECT Expense_name, Who_paid, Person_cost, Date FROM Expenses WHERE id = {};".format(expenseID))
        expense = cursor.fetchone()
        description = str(expense[0])
        who_paid = expense[1]
        person_cost = round(expense[2], 2)
        date = str(expense[3])
        total_paid += person_cost

        cursor.execute("SELECT Venmo FROM Users WHERE Name = \"{}\";".format(who_paid))
        venmo = str(cursor.fetchone()[0])

        cost = person_cost * num_shares
        display_row = []
        display_row.append(date)
        display_row.append(cost)
        display_row.append(description)
        display_row.append(venmo)
        display_row.append(expenseID)
        all_display_info.append(display_row)
    cursor.close()
    return all_display_info


def get_users(conn, groupID):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Users WHERE groupID = {};".format(groupID))
    result = cursor.fetchall()
    ids = []
    for row in result:
        ids.append(row[0])
    cursor.close()
    return ids

def get_password_hash(conn, userID):
    cursor = conn.cursor()
    cursor.execute("SELECT Hash FROM Users WHERE id = {}".format(userID))
    result = cursor.fetchone()
    if not result:
        hash = result[0]
    cursor.close()
    return hash

def user_exists(conn, venmo):
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM Users WHERE Venmo = \"{}\";".format(venmo))
    if not cursor.fetchone():
        cursor.close()
        return False
    else:
        cursor.close()
        return True

def has_registered(conn, venmo):
    cursor = conn.cursor()
    cursor.execute("SELECT Username FROM Users WHERE Venmo = \"{}\";".format(venmo))
    if (cursor.fetchone()):
        cursor.close()
        return True
    else:
        cursor.close()
        return False

def register_user(conn, venmo, username, hash):
    if has_registered(conn, venmo):
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET Hash = \"{}\", Username = \"{}\" WHERE Venmo = \"{}\";".format(hash, username, venmo))
        cursor.close()
        return

def get_groups(conn, venmo):
    cursor = conn.cursor()
    cursor.execute("SELECT groupID FROM Users WHERE venmo = \"{}\";".format(venmo))
    result = cursor.fetchall()
    groups = []
    for group in result:
        groups.append(group[0])
    cursor.close()
    return groups

def group_id_to_name(conn, groupID):
    cursor = conn.cursor()
    cursor.execute("SELECT Group_name FROM Groups WHERE id = {};".format(groupID))
    name = cursor.fetchone()[0]
    cursor.close()
    return name


def get_expense_info(conn, expenseID):
    cursor = conn.cursor()
    cursor.execute("SELECT Amount, Expense_name, Who_paid, Person_cost, Date FROM Expenses WHERE id = {};".format(expenseID))
    expense = cursor.fetchall()

    cursor.execute("SELECT groupID FROM Expenses WHERE id = {};".format(expenseID))
    groupID = cursor.fetchone()[0]
    users = get_users(conn, groupID)
    paid_yn = []
    for user in users:
        venmo = id_to_venmo(conn, user)
        cursor.execute("SELECT Paid FROM Dues WHERE Venmo = \"{}\" AND expenseID = {};".format(venmo, expenseID))
        value = cursor.fetchone()
        if value is not None:
            if value[0] == 0:
                has_paid = False
            else:
                has_paid = True
        else:
            has_paid = True
        paid_yn.append(has_paid)
    
    expense_info = []
    for info in expense[0]:
        expense_info.append(info)
    
    expense_info.append(paid_yn)

    cursor.close()
    return expense_info

def id_to_venmo(conn, userID):
    cursor = conn.cursor()
    cursor.execute("SELECT Venmo FROM Users WHERE id = {};".format(userID))
    venmo = cursor.fetchone()[0]
    return venmo
        
def group_name_to_id(conn, groupName):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Groups WHERE Group_name = \"{}\";".format(groupName))       
    id = cursor.fetchone()[0]
    return id 





    
if (__name__ == "__main__"):
    print("ok cool")


#TODO create an AllPaid function

#TODO create AddUser function

#TODO create simple functions to return cell values

#TODO calculate who owes you how much and how much you owe someone

#TODO need something that returns group not found

