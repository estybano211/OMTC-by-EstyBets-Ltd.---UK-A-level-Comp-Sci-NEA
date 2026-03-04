import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
import logging
from queue import Queue
from threading import Thread, Event

# Database file paths
DB_FILE = "OMTC_database.db"


class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that writes custom log messages directly into the 'db_logs'
    table. It uses a queue-based worker thread to prevent database locking issues
    during concurrent operations. All log entries are processed asynchronously
    to avoid blocking the main application thread.
    """

    def __init__(self):
        """
        Initialises the database log handler with a queue and worker thread.
        Creates a daemon thread that continuously processes log entries from
        the queue and writes them to the database one at a time.
        """
        super().__init__()

        self.DB_FILE = DB_FILE

        self.queue = Queue()

        self.stop_event = Event()

        self.worker_thread = Thread(target=self.processor, daemon=True)

        self.worker_thread.start()

    def emit(self, record: logging.LogRecord):
        """
        Captures a log record, formats it, and adds it to the processing queue.
        Then extracts the log level and current timestamp, then queues the entry
        to write to the database. If an error occurs during emit, it is then
        handled to prevent program crashes.

        Args:
            record (logging.LogRecord): The log record object containing the
                                        custom log message and metadata.
        """
        try:
            log_entry = self.format(record)

            level = record.levelname

            timestamp = datetime.now().strftime("%d-%m-%Y | %H:%M:%S")

            self.queue.put((timestamp, level, log_entry))

        except Exception:
            self.handleError(record)

    def processor(self):
        """
        Worker thread that processes the queue and writes logs to the database
        one at a time to avoid locking issues. Runs continuously until the
        stop_event is set to prevent the thread from hanging indefinitely.
        """
        while not self.stop_event.is_set():
            try:
                # Wait for a log entry (timeout prevents thread from hanging forever).
                timestamp, level, log_entry = self.queue.get(timeout=1)

                with sqlite3.connect(self.DB_FILE, timeout=5) as conn:
                    conn.execute(
                        """
                        INSERT INTO db_logs(timestamp, level, log_entry)
                        VALUES (?, ?, ?)
                        """,
                        (timestamp, level, log_entry),
                    )
                    conn.commit()

                self.queue.task_done()
            except Exception:
                pass

    def close(self):
        """
        Stops the worker thread and closes the handler. Sets the stop event to
        signal the worker thread to exit, then waits for it to finish before
        calling the parent class's close method.
        """
        self.stop_event.set()
        self.worker_thread.join()
        super().close()


# Create a named logger for the database module.
database_logger = logging.getLogger("omtc_db")

database_logger.setLevel(logging.DEBUG)

if not database_logger.handlers:
    db_handler = DatabaseLogHandler()

    db_handler.setLevel(logging.DEBUG)

    db_formatter = logging.Formatter("%(message)s")

    db_handler.setFormatter(db_formatter)
    database_logger.addHandler(db_handler)


def get_database_logger():
    """
    Returns the configured database logger instance. This logger writes to the
    'db_logs' table and can be imported by other modules.

    Returns:
        logging.Logger: The database logger instance configured with
                        DatabaseLogHandler.
    """
    return database_logger


class AdminLogHandler(logging.Handler):
    """
    Custom logging handler that writes log messages directly into the
    'admin_logs' table. Uses a queue-based worker thread to prevent database
    locking issues during concurrent operations. All admin action entries are
    processed asynchronously to avoid blocking the main application thread.
    """

    def __init__(self):
        """
        Initialises the admin log handler with a queue and worker thread.
        Creates a daemon thread that continuously processes admin log entries
        from the queue and writes them to the database one at a time.
        """
        super().__init__()

        self.DB_FILE = DB_FILE

        self.queue = Queue()

        self.stop_event = Event()

        self.worker_thread = Thread(target=self.processor, daemon=True)

        self.worker_thread.start()

    def emit(self, record: logging.LogRecord):
        """
        Captures an admin log record, formats it, and adds it to the processing
        queue. Extracts the log level and current timestamp, then queues the
        entry for database insertion. If an error occurs during emit, it is
        handled gracefully to prevent program crashes.

        Args:
            record (logging.LogRecord): The log record object containing the
                                        admin action message and metadata.
        """
        try:
            log_entry = self.format(record)

            level = record.levelname

            timestamp = datetime.now().strftime("%d-%m-%Y | %H:%M:%S")

            self.queue.put((timestamp, level, log_entry))

        except Exception:
            self.handleError(record)

    def processor(self):
        """
        Worker thread that processes the queue and writes admin logs to the
        database one at a time. Runs continuously until the stop_event is set
        to prevent the thread from hanging indefinitely.
        """
        while not self.stop_event.is_set():
            try:
                timestamp, level, log_entry = self.queue.get(timeout=1)

                with sqlite3.connect(self.DB_FILE, timeout=5) as conn:
                    conn.execute(
                        """
                        INSERT INTO admin_logs(timestamp, level, log_entry)
                        VALUES (?, ?, ?)""",
                        (timestamp, level, log_entry),
                    )
                    conn.commit()

                self.queue.task_done()

            except Exception:
                pass

    def close(self):
        """
        Stops the worker thread and closes the handler. Sets the stop event to
        signal the worker thread to exit, then waits for it to finish before
        calling the parent class's close method.
        """
        self.stop_event.set()
        self.worker_thread.join()
        super().close()


# Create a named logger for admin actions.
admin_logger = logging.getLogger("omtc_admin")

admin_logger.setLevel(logging.DEBUG)

if not admin_logger.handlers:
    admin_handler = AdminLogHandler()
    admin_handler.setLevel(logging.DEBUG)

    admin_formatter = logging.Formatter("%(message)s")
    admin_handler.setFormatter(admin_formatter)

    admin_logger.addHandler(admin_handler)


class DatabaseManagement:
    """
    Handles all database creation, connection, and data operations.
    Manages user accounts, game statistics, logging tables, and
    provides methods for querying, updating, and maintaining the SQLite
    database.
    """

    def __init__(self):
        """
        Initialises the DatabaseManagement class with the database file path.
        """
        self.DB_FILE = DB_FILE

    def check_database_exists(self):
        """
        Checks if the database file exists in the same directory as the
        program. Constructs the full database path and verifies file existence.

        Returns:
            bool: True if the database file exists, False otherwise.
        """
        program_dir = os.path.dirname(os.path.abspath(__file__))

        DB_FILE = os.path.join(program_dir, os.path.basename(self.DB_FILE))

        return os.path.exists(DB_FILE)

    # SQL Database Schema.
    # Each dictionary value is a CREATE TABLE statement run during database creation.
    SCHEMA = {
        # Logs for database access and amendments.
        "db_logs": """
        CREATE TABLE IF NOT EXISTS db_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            log_entry TEXT
        )  
        """,
        # Logs for administrative actions.
        "admin_logs": """
        CREATE TABLE IF NOT EXISTS admin_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT NOT NULL,
            log_entry TEXT
        )
        """,
        # Users account table.
        "users": """
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            registered INTEGER,
            balance REAL DEFAULT 10000 CHECK (balance >= 0),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            terminated INTEGER DEFAULT 0,
            terminated_at TEXT,
            termination_reason TEXT
        )
        """,
        # Poker data per user.
        "user_poker_data": """
        CREATE TABLE IF NOT EXISTS user_poker_data(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            rounds_played INTEGER DEFAULT 0,
            player_range TEXT,
            vpip REAL DEFAULT 0,
            pfr REAL DEFAULT 0,
            total_hands_played INTEGER DEFAULT 0,
            total_hands_raised INTEGER DEFAULT 0,
            total_bets INTEGER DEFAULT 0,
            fold_to_raise INTEGER DEFAULT 0,
            call_when_weak INTEGER DEFAULT 0,
            gauntlet_max_rounds INTEGER DEFAULT 0,
            endless_high_score INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """,
        # Logs of user poker actions during hands.
        "user_poker_actions": """
        CREATE TABLE IF NOT EXISTS user_poker_actions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            round_number INTEGER,
            street TEXT,
            action TEXT,
            bet_size REAL,
            pot_size REAL,
            resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """,
    }

    def connect(self):
        """
        Establishes a connection to the SQLite database. Enables row factory
        for dictionary-like row access and enforces foreign key constraints.

        Returns:
            sqlite3.Connection: Database connection object with Row factory and
                                foreign keys enabled.
        """
        conn = sqlite3.connect(DB_FILE)

        conn.row_factory = sqlite3.Row

        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_database(self):
        """
        Creates all tables defined in the SCHEMA dictionary if they do not
        already exist. Iterates through each table definition, executes the
        CREATE TABLE statement, then creates the default administrator account.
        Logs each table creation and the overall database creation event.
        """
        with self.connect() as conn:
            try:
                for table_name, table in self.SCHEMA.items():
                    conn.execute(table)

                    database_logger.info(f"Table: '{table_name}' created.")

                conn.commit()

                database_logger.info(f"File: '{DB_FILE}' created.")

                self.admin_account()

                database_logger.info("Administrator account added to 'users' table.")

            except sqlite3.Error as e:
                database_logger.exception("'create_database' error.")

    def admin_account(self):
        """
        Ensures that a default Administrator account exists in the database.
        Creates the account with a predefined password if it does not already
        exist. The password should be changed after first use.
        """
        admin_password = "Goober"

        from check_systems_V6 import hash_function

        hashed_password = hash_function(admin_password)

        with self.connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT 1 FROM users
                    WHERE username = ?
                    """,
                    ("Administrator",),
                )

                if cursor.fetchone() is None:
                    conn.execute(
                        """
                        INSERT INTO users
                        (username, password_hash, registered, balance) 
                        VALUES (?, ?, ?, ?)
                        """,
                        ("Administrator", (hashed_password), 1, 0.0),
                    )

                    database_logger.info("Administrator account created.")

            except sqlite3.Error as e:
                database_logger.exception("'admin_account' error.")

    def admin_logged_in(self):
        """
        Creates a log entry in the admin_logs table recording that the
        administrator has successfully logged in.
        """
        admin_logger.info("Administrator logged in.")

    def admin_accessed_system(self, system):
        """
        Creates a log entry recording when the administrator accesses a
        specific system.

        Args:
            system (str): The name of the system accessed by the administrator.
        """
        admin_logger.info(f"Administrator accessed system: '{system}'.")

    def change_admin_password(self, new_password):
        """
        Changes the administrator password to a new hashed value. Hashes the
        new password before storing it in the database. Logs the request and
        outcome to both the admin and database loggers.

        Args:
            new_password (str): The new plaintext password to be hashed and
                                stored.
        """
        with self.connect() as conn:
            try:
                admin_logger.info("Administrator requesting to change Admin Password.")

                database_logger.info(f"Request to change Administrator password.")

                from check_systems_V6 import hash_function

                password_hash = hash_function(new_password)

                conn.execute(
                    """
                    UPDATE users 
                    SET password_hash = ? 
                    WHERE username = ?
                    """,
                    (password_hash, "Administrator"),
                )

                database_logger.info("Administrator password changed.")

                admin_logger.info("Administrator password change request granted.")

            except sqlite3.Error as e:
                admin_logger.error("Administrator password change request denied.")

                database_logger.exception("'change_admin_password' error.")

    def view_database(self, table):
        """
        Returns a DataFrame of all rows in the requested table for
        administrator viewing. Logs the request and outcome to both the admin
        and database loggers.

        Args:
            table (str): The name of the database table to view.

        Returns:
            pd.DataFrame: DataFrame containing all rows from the specified
                          table, or an empty DataFrame on error or if no table
                          is provided.
        """
        if not table:
            database_logger.error("No table provided for admin_view_database().")
            return pd.DataFrame()

        with self.connect() as conn:
            try:
                admin_logger.info(f"Administrator requesting to view Table: '{table}'")

                database_logger.info(f"Attempting to read data from Table: '{table}'.")

                dataframe = pd.read_sql_query(f"SELECT * FROM {table}", conn)

                database_logger.info(f"Data from Table: '{table}' read successfully.")

                admin_logger.info("View table request granted.")

                return dataframe

            except sqlite3.Error as e:
                admin_logger.error("View table request denied.")

                database_logger.exception("'view_database' error.")
                return pd.DataFrame()

    def change_user_record(
        self,
        *,
        user_id,
        new_username=None,
        new_password=None,
        new_account_type=None,
        new_balance=None,
        terminated=None,
        reason=None,
    ):
        """
        Updates one or more fields on a user record by delegating to the
        relevant individual change methods for each non-None argument. Fields
        that are passed as None are left unchanged.

        Args:
            user_id (int): The user ID of the record to modify.
            new_username (str, optional): New username to assign.
            new_password (str, optional): New plaintext password (will be
                                          hashed before storage).
            new_account_type (int, optional): New registered status (0 or 1).
            new_balance (float, optional): New balance value.
            terminated (int, optional): Termination flag (0 = active,
                                        1 = terminated).
            reason (str, optional): Reason for termination, required when
                                    terminated is set to 1.
        """

        if new_username is not None:
            self.change_user_username(user_id, new_username)

        if new_password is not None:
            self.change_user_password(user_id, new_password)

        if new_account_type is not None:
            self.change_user_account_type(user_id, new_account_type)

        if new_balance is not None:
            self.change_user_balance(user_id, new_balance)

        if terminated is not None:
            self.change_user_status(user_id, terminated, reason)

    def change_user_id(self, old_user_id, new_user_id):
        """
        Changes a user's ID from old_user_id to new_user_id. Logs the request
        and outcome to both the admin and database loggers.

        Args:
            old_user_id (int): The current user ID to change.
            new_user_id (int): The new user ID to assign.
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to change User ID: '{old_user_id}' to '{new_user_id}'."
                )

                database_logger.info(
                    f"Request to change User ID: '{old_user_id}' to '{new_user_id}'."
                )

                conn.execute(
                    """
                    UPDATE users
                    SET user_id = ?
                    WHERE user_id = ?
                    """,
                    (new_user_id, old_user_id),
                )

                admin_logger.info("Change user ID request granted.")

                database_logger.info(
                    f"User ID: '{old_user_id}' changed to '{new_user_id}'."
                )

            except sqlite3.Error as e:
                admin_logger.error("Change user ID request denied.")

                database_logger.exception("'change_user_id' error.")

    def change_user_username(self, user_id, new_username):
        """
        Changes a user's username to the given value. Logs the request and
        outcome to both the admin and database loggers.

        Args:
            user_id (int): The user ID whose username will be changed.
            new_username (str): The new username to assign.
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to change User ID: '{user_id}' username."
                )

                database_logger.info(
                    f"Request to change User ID: '{user_id}' username."
                )

                conn.execute(
                    """
                    UPDATE users
                    SET username = ?
                    WHERE user_id = ?
                    """,
                    (new_username, user_id),
                )

                admin_logger.info("Change user username request granted.")

                database_logger.info(f"User ID: '{user_id}' username changed.")

            except sqlite3.Error as e:
                admin_logger.error("Change user username request denied.")

                database_logger.exception("'change_user_username' error.")

    def change_user_password(self, user_id, new_password):
        """
        Changes a user's password to a new hashed value. Hashes the new
        password before storing it in the database. Logs the request and
        outcome to both the admin and database loggers.

        Args:
            user_id (int): The user ID whose password will be changed.
            new_password (str): The new plaintext password to be hashed and
                                stored.
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to change User: '{user_id}' password."
                )

                database_logger.info(f"Request to change User: '{user_id}' password.")

                from check_systems_V6 import hash_function

                password_hash = hash_function(new_password)

                conn.execute(
                    """
                    UPDATE users
                    SET password_hash = ?
                    WHERE user_id = ?
                    """,
                    (password_hash, user_id),
                )

                admin_logger.info("Change user password request granted.")

                database_logger.info(f"User: '{user_id}' password changed.")

            except sqlite3.Error as e:
                admin_logger.error("Change user password request denied.")

                database_logger.exception("'change_user_password' error.")

    def change_user_account_type(self, user_id, registered):
        """
        Changes a user's account type (registered status). Logs the request
        and outcome to both the admin and database loggers.

        Args:
            user_id (int): The user ID whose account type will be changed.
            registered (int): The new registered status (0 for guest,
                              1 for registered).
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to change User ID: '{user_id}' account type."
                )

                database_logger.info(
                    f"Request to change User ID: '{user_id}' account type."
                )

                conn.execute(
                    """
                    UPDATE users 
                    SET registered = ? 
                    WHERE user_id = ?
                    """,
                    (registered, user_id),
                )

                admin_logger.info("Change user account type request granted.")

                database_logger.info(f"User ID: '{user_id}' account type changed.")

            except sqlite3.Error as e:
                admin_logger.error("Change user account type request denied.")

                database_logger.exception("'change_user_account_type' error.")

    def change_user_balance(self, user_id, new_balance):
        """
        Changes a user's account balance to the specified value. Logs the
        request and outcome to both the admin and database loggers.

        Args:
            user_id (int): The user ID whose balance will be changed.
            new_balance (float): The new balance to assign.
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to change User ID: '{user_id}' balance."
                )

                database_logger.info(f"Request to change User ID: '{user_id}' balance.")

                conn.execute(
                    """
                    UPDATE users 
                    SET balance = ? 
                    WHERE user_id = ?
                    """,
                    (float(new_balance), user_id),
                )

                admin_logger.info("Change user balance request granted.")

                database_logger.info(f"User ID: '{user_id}' balance changed.")

            except sqlite3.Error as e:
                admin_logger.error("Change user balance request denied.")

                database_logger.exception("'change_user_balance' error.")

    def change_user_status(self, user_id, terminated, reason=None):
        """
        Changes a user's termination status. If terminated is truthy, sets the
        termination timestamp and reason. If falsy, clears all termination
        data. Logs the request and outcome to both the admin and database
        loggers.

        Args:
            user_id (int): The user ID whose status will be changed.
            terminated (int): Termination flag (0 for active, 1 for
                              terminated).
            reason (str, optional): Reason for termination. Required when
                                    terminated is 1.
        """
        with self.connect() as conn:
            try:
                timestamp = datetime.now().strftime("%d-%m-%Y | %H:%M:%S")

                admin_logger.info(
                    f"Administrator requesting to change User ID: '{user_id}' status."
                )

                database_logger.info(f"Request to change User ID: '{user_id}' status.")

                if terminated:
                    conn.execute(
                        """
                        UPDATE users 
                        SET terminated = 1, terminated_at = ?, termination_reason = ? 
                        WHERE user_id = ?
                        """,
                        (timestamp, reason, user_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE users 
                        SET terminated = 0, terminated_at = NULL, termination_reason = NULL 
                        WHERE user_id = ?
                        """,
                        (user_id,),
                    )

                admin_logger.info("Change user status request granted.")

                database_logger.info(f"User ID: '{user_id}' status changed.")

            except sqlite3.Error as e:
                admin_logger.error("Change user status request denied.")

                database_logger.exception("'change_user_status' error.")

    def delete_user_record(self, user_id):
        """
        Permanently deletes a user record from the users table by user ID.
        Logs the request and outcome to both the admin and database loggers.

        Args:
            user_id (int): The user ID to delete from the database.
        """
        with self.connect() as conn:
            try:
                admin_logger.info(
                    f"Administrator requesting to delete User ID: '{user_id}' record."
                )

                database_logger.info(f"Request to delete User: '{user_id}' record.")

                conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                admin_logger.info("Delete user record request granted.")

                database_logger.info(f"User ID: '{user_id}' record deleted.")

            except sqlite3.Error as e:
                admin_logger.error("Delete user record request denied.")

                database_logger.exception("'delete_user_record' error.")

    def get_user_full_record(self, *, user_id=None, username=None):
        """
        Retrieves the complete user record for a given user_id or username.
        Returns all columns from the users table as a dictionary.

        Args:
            user_id (int, optional): The user ID to search for.
            username (str, optional): The username to search for.

        Returns:
            dict: Dictionary containing all user fields, or None if the user
                  was not found or an error occurred.

        Raises:
            ValueError: If neither user_id nor username is provided.
        """
        if user_id is None and username is None:
            raise ValueError("Either user_id or username must be provided")

        with self.connect() as conn:
            try:
                if user_id is not None:
                    cursor = conn.execute(
                        "SELECT * FROM users WHERE user_id = ?", (user_id,)
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM users WHERE username = ?", (username,)
                    )

                row = cursor.fetchone()
                return dict(row) if row else None

            except sqlite3.Error:
                database_logger.exception("'get_user_full_record' error.")
                return None

    def get_user_presence(self, username=None):
        """
        Checks whether a user with the given username exists in the database.
        Logs the search and result to the database logger.

        Args:
            username (str, optional): The username to search for.

        Returns:
            dict: A dictionary with a single key 'found' (bool), True if the
                  user exists, False otherwise.
        """
        with self.connect() as conn:
            try:
                database_logger.info(f"Searching for User: '{username}'.")

                cursor = conn.execute(
                    """
                    SELECT 1 
                    FROM users 
                    WHERE username = ?
                    """,
                    (username,),
                )

                row = cursor.fetchone()
                found = row is not None

                if found:
                    database_logger.info(f"User '{username}' found.")
                else:
                    database_logger.info(f"User '{username}' not found.")

                return {"found": found}

            except sqlite3.Error as e:
                database_logger.exception("'get_user_presence' error.")
                return {"found": False}

    def sign_in_user(self, username, password, registered):
        """
        Registers a new user in the database with a hashed password, registered
        status, and an initial balance of £10,000. Guest accounts may be created
        with a None password.

        Args:
            username (str): The username for the new account (must be unique).
            password (str or None): The plaintext password to hash and store.
                                    Pass None for guest accounts.
            registered (int): Registration status (0 for guest, 1 for
                               registered).

        Returns:
            str: The username of the created account.

        Raises:
            ValueError: If username is not a non-empty string.
            sqlite3.IntegrityError: If the username already exists.
            sqlite3.Error: For other database errors.
        """
        if not username or not isinstance(username, str):
            raise ValueError("'username' must be a non-empty string")

        if username.strip().lower() == "administrator":
            raise ValueError("The username 'Administrator' cannot be used.")

        from check_systems_V6 import hash_function

        password_hash = hash_function(password) if password else None

        INIT_BALANCE = 10000.0

        with self.connect() as conn:
            try:
                database_logger.info(
                    f"Request to make an account for User: '{username}'."
                )

                conn.execute(
                    """
                    INSERT INTO users
                    (username, password_hash, registered, balance) 
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        username,
                        password_hash,
                        int(float(registered)),
                        float(INIT_BALANCE),
                    ),
                )

                database_logger.info(f"Created User: '{username}' record.")

                return username

            except sqlite3.IntegrityError:
                database_logger.warning(f"User: '{username}' record already exists.")
                raise

            except sqlite3.Error as e:
                database_logger.exception("'sign_in_user' error. ")
                raise

    def verify_user_password(self, username, password):
        """
        Verifies whether a provided plaintext password matches the stored hash
        for the given username. Uses constant-time comparison to prevent timing
        attacks. Logs the verification attempt and result.

        Args:
            username (str): The username whose password will be verified.
            password (str): The plaintext password to verify.

        Returns:
            dict: Dictionary with 'found' (bool) and 'verified' (bool) keys.
        """
        with self.connect() as conn:
            try:
                database_logger.info(
                    f"Request to search for User: '{username}' 'password_hash'."
                )

                cursor = conn.execute(
                    """
                    SELECT password_hash 
                    FROM users 
                    WHERE username = ?
                    """,
                    (username,),
                )

                row = cursor.fetchone()

            except sqlite3.Error as e:
                database_logger.exception("'verify_user_password' error.")
                return {"found": False, "verified": False}

        if not row or not row["password_hash"]:
            database_logger.info(f"'password_hash' for User: '{username}' not found.")
            return {"found": False, "verified": False}

        from check_systems_V6 import verify_hash

        verified = verify_hash(row["password_hash"], password)

        if verified:
            database_logger.info(
                f"Password verification successful for User: '{username}'."
            )
        else:
            database_logger.info(f"Failed password attempt for User: '{username}'.")

        return {"found": True, "verified": verified}

    def reset_user_password(self, user_id, new_password):
        """
        Resets a user's password to the given value. Hashes the new password
        before storing it. Logs the request and outcome to the database logger.

        Args:
            user_id (int): The user ID whose password will be reset.
            new_password (str): The new plaintext password to hash and store.
        """
        with self.connect() as conn:
            try:
                database_logger.info(
                    f"User request to reset User ID: '{user_id}' password."
                )

                from check_systems_V6 import hash_function

                password_hash = hash_function(new_password)

                conn.execute(
                    """
                    UPDATE users 
                    SET password_hash = ? 
                    WHERE user_id = ?
                    """,
                    (password_hash, user_id),
                )

                database_logger.info(
                    f"Password for User ID: '{user_id}' reset successfully."
                )

            except sqlite3.Error as e:
                database_logger.exception("'reset_user_password' error.")

    def get_user_id(self, username):
        """
        Retrieves the user ID for the given username. Logs the request and
        result to the database logger.

        Args:
            username (str): The username to look up.

        Returns:
            dict: Dictionary with 'found' (bool) and 'user_id' (int or None)
                  keys.
        """
        with self.connect() as conn:
            try:
                database_logger.info(f"Request to get User: '{username}' user_id.")

                cursor = conn.execute(
                    """
                    SELECT user_id 
                    FROM users 
                    WHERE username = ?
                    """,
                    (username,),
                )
                row = cursor.fetchone()

                if row:
                    database_logger.info(f"'user_id' for User: '{username}' found.")
                    return {"found": True, "user_id": row["user_id"]}
                else:
                    database_logger.info(f"'user_id' for User: '{username}' not found.")
                    return {"found": False, "user_id": None}

            except sqlite3.Error as e:
                database_logger.exception("'get_user_id' error.")
                return {"found": False, "user_id": None}

    def get_username(self, user_id):
        """
        Retrieves the username for the given user ID. Logs the request and
        result to the database logger.

        Args:
            user_id (int): The user ID to look up.

        Returns:
            dict: Dictionary with 'found' (bool) and 'username' (str or None)
                  keys.
        """
        with self.connect() as conn:
            try:
                database_logger.info(f"Request to get User ID: '{user_id}' username.")

                cursor = conn.execute(
                    """
                    SELECT username 
                    FROM users 
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()

                if row:
                    database_logger.info(f"'username' for User ID: '{user_id}' found.")
                    return {"found": True, "username": row["username"]}
                else:
                    database_logger.info(
                        f"'username' for User ID: '{user_id}' not found."
                    )
                    return {"found": False, "username": None}

            except sqlite3.Error as e:
                database_logger.exception("'get_username' error.")
                return {"found": False, "username": None}

    def get_user_balance(self, username):
        """
        Retrieves the account balance for the given username. Logs the request
        and result to the database logger.

        Args:
            username (str): The username whose balance will be retrieved.

        Returns:
            dict: Dictionary with 'found' (bool) and 'balance' (float) keys.
                  Balance defaults to 0.0 if the user is not found or an error
                  occurs.
        """
        with self.connect() as conn:
            try:
                database_logger.info(f"Request to get User: '{username}' balance.")

                cursor = conn.execute(
                    """
                    SELECT balance 
                    FROM users 
                    WHERE username = ?
                    """,
                    (username,),
                )
                row = cursor.fetchone()

                if row:
                    database_logger.info(f"'balance' for User: '{username}' found.")
                    return {"found": True, "balance": float(row["balance"])}
                else:
                    database_logger.info(f"'balance' for User: '{username}' not found.")
                    return {"found": False, "balance": 0.0}

            except sqlite3.Error as e:
                database_logger.exception("'get_user_balance' error.")
                return {"found": False, "balance": 0.0}

    def modify_user_balance(self, username, new_balance):
        """
        Updates a user's account balance to the specified value. Logs the
        request and outcome to the database logger.

        Args:
            username (str): The username whose balance will be modified.
            new_balance (float): The new balance to assign.
        """
        with self.connect() as conn:
            try:
                database_logger.info(f"Request to modify User: '{username}' balance.")

                conn.execute(
                    """
                    UPDATE users 
                    SET balance = ? 
                    WHERE username = ?
                    """,
                    (float(new_balance), username),
                )

                database_logger.info(f"Balance for User: {username} modified.")
                return

            except sqlite3.Error as e:
                database_logger.exception("'modify_user_balance' error.")

    def terminate_user_account(self, username, reason):
        """
        Marks a user's account as terminated, recording the current timestamp
        and the reason for termination. Logs the request and outcome to the
        database logger.

        Args:
            username (str): The username whose account will be terminated.
            reason (str): The reason for account termination.
        """
        with self.connect() as conn:
            try:
                timestamp = datetime.now().strftime("%d-%m-%Y | %H:%M:%S")

                database_logger.info(
                    f"Request to terminate User: '{username}' account."
                )

                conn.execute(
                    """
                    UPDATE users 
                    SET terminated = 1, terminated_at = ?, termination_reason = ? 
                    WHERE username = ?
                    """,
                    (timestamp, reason, username),
                )

                database_logger.info(f"User: '{username}' account terminated.")
                return

            except sqlite3.Error as e:
                database_logger.exception("'terminate_user_account' error.")

    def admin_password_check(self, password):
        """
        Verifies a provided password against the stored administrator password
        hash. Logs the verification attempt and result to the database logger.

        Args:
            password (str): The plaintext password to verify.

        Returns:
            dict: Dictionary with 'found' (bool) and 'verified' (bool) keys.
        """
        with self.connect() as conn:
            try:
                database_logger.info("Request for Administrator password_hash.")

                cursor = conn.execute(
                    """
                    SELECT password_hash
                    FROM users 
                    WHERE username = ?
                    """,
                    ("Administrator",),
                )

                row = cursor.fetchone()

            except sqlite3.Error as e:
                database_logger.exception("'admin_password_check' error.")
                return {"found": False, "verified": False}

        if not row or not row["password_hash"]:
            database_logger.debug("'password_hash' for Administrator not found.")
            return {"found": False, "verified": False}

        from check_systems_V6 import verify_hash

        verified = verify_hash(row["password_hash"], password)

        if verified:
            database_logger.info("Password verification successful for Administrator.")
        else:
            database_logger.info("Failed password attempt from Administrator.")

        return {"found": True, "verified": verified}

    def user_password_check(self, username, password):
        """
        Compatibility wrapper around :func:`verify_user_password`.
        Historically this method only checked unregistered (guest) accounts,
        which caused login failures for normal registered users.  It now
        delegates to the general verification routine so behaviour is consistent
        regardless of registration state.

        Args:
            username (str): The username whose password will be verified.
            password (str): The plaintext password to verify.

        Returns:
            dict: Dictionary with 'found' (bool) and 'verified' (bool) keys.
        """

        return self.verify_user_password(username, password)

        if not row or not row["password_hash"]:
            database_logger.info(
                f"User: {username} not found or password_hash missing."
            )
            return {"found": False, "verified": False}

        from check_systems_V6 import verify_hash

        verified = verify_hash(row["password_hash"], password)

        if verified:
            database_logger.info(
                f"Password verification successful for user: {username}"
            )
        else:
            database_logger.info(f"Failed password attempt for user: {username}")

        return {"found": True, "verified": verified}

    def check_user_poker_data_exists(self, user_id):
        """
        Checks whether a poker data record exists for the given user ID.

        Args:
            user_id (int): The user ID to check.

        Returns:
            bool: True if a record exists, False otherwise or on error.
        """
        with self.connect() as conn:
            try:
                exists = conn.execute(
                    """
                    SELECT 1 FROM user_poker_data WHERE user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                return exists is not None

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error checking poker data for user {user_id}: {e}"
                )
                return False

    def initialise_user_poker_data(self, user_id):
        """
        Creates a new poker data record for the given user with default values
        and a freshly generated base range chart. If a record already exists,
        no changes are made. Logs the outcome to the database logger.

        Args:
            user_id (int): The user ID to initialise poker data for.

        Returns:
            bool: True if initialisation was successful or data already exists,
                  False on error.
        """
        with self.connect() as conn:
            try:
                exists = conn.execute(
                    """
                    SELECT 1 FROM user_poker_data WHERE user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                if exists:
                    database_logger.info(f"User {user_id} poker data already exists")
                    return True

                conn.execute(
                    """
                    INSERT INTO user_poker_data (user_id)
                    VALUES (?)
                """,
                    (user_id,),
                )

                from poker_player_management_V6 import generate_range_chart

                # Create a base range chart
                conn.execute(
                    """
                    UPDATE user_poker_data
                    SET player_range = ?
                    WHERE user_id = ?
                """,
                    (json.dumps(generate_range_chart()), user_id),
                )

                database_logger.info(f"Initialized poker data for user {user_id}")
                return True

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error initializing poker data for user {user_id}: {e}"
                )
                return False

    def load_user_poker_data(self, user_id):
        """
        Loads the complete poker data record for a user. This is the primary
        method used during PokerPlayer initialisation. Retrieves all stored
        statistics, calculates derived values (avg_bet_size), and normalises
        fold_to_raise and call_when_weak to a 0.0–1.0 range.

        Args:
            user_id (int): The user ID to load data for.

        Returns:
            dict: Dictionary containing all poker data fields plus derived
                  statistics (avg_bet_size), with player_range
                  deserialised from JSON. Returns None if the user is not found
                  or an error occurs.
        """
        with self.connect() as conn:
            try:
                # Get user data with poker stats
                row = conn.execute(
                    """
                    SELECT
                        upd.user_id,
                        upd.rounds_played,
                        upd.player_range,
                        upd.vpip,
                        upd.pfr,
                        upd.total_hands_played,
                        upd.total_hands_raised,
                        upd.total_bets,
                        upd.fold_to_raise,
                        upd.call_when_weak,
                        upd.last_updated
                    FROM user_poker_data upd
                    WHERE upd.user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                if not row:
                    database_logger.warning(f"User {user_id} not found in poker data")
                    return None

                # Convert to dictionary
                record = dict(row)

                # Parse player_range JSON
                record["player_range"] = (
                    json.loads(record["player_range"])
                    if record.get("player_range")
                    else None
                )

                # Calculate derived statistics
                rounds = max(1, record["rounds_played"])
                record["avg_bet_size"] = record["total_bets"] / rounds

                # Normalize fold_to_raise and call_when_weak to 0.0-1.0
                # These are stored as counts, convert to frequencies
                total_pressure_situations = (
                    record["fold_to_raise"] + record["call_when_weak"]
                )
                if total_pressure_situations > 0:
                    record["fold_to_raise"] = (
                        record["fold_to_raise"] / total_pressure_situations
                    )
                    record["call_when_weak"] = (
                        record["call_when_weak"] / total_pressure_situations
                    )
                else:
                    # Default values if no data
                    record["fold_to_raise"] = 0.5
                    record["call_when_weak"] = 0.5

                return record

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error loading poker data for user {user_id}: {e}"
                )
                return None
            except json.JSONDecodeError as e:
                database_logger.exception(
                    f"Error parsing player_range JSON for user {user_id}: {e}"
                )
                return None

    def update_player_range(self, user_id, player_range):
        """
        Serialises and stores a player's range chart in the database, updating
        the last_updated timestamp.

        Args:
            user_id (int): The user ID whose range will be updated.
            player_range (dict): The range dictionary to store.

        Returns:
            bool: True if successful, False on error.
        """
        with self.connect() as conn:
            try:
                range_json = json.dumps(player_range)

                conn.execute(
                    """
                    UPDATE user_poker_data
                    SET 
                        player_range = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """,
                    (range_json, user_id),
                )

                return True

            except (sqlite3.Error, json.JSONDecodeError) as e:
                database_logger.exception(
                    f"Error updating player range for user {user_id}: {e}"
                )
                return False

    def log_player_action(
        self, *, user_id, round_number, street, action, bet_size, pot_size
    ):
        """
        Logs a single player action to the user_poker_actions table.

        Args:
            user_id (int): The user ID performing the action.
            round_number (int): The unique hand/round identifier.
            street (str): The current betting round ('preflop', 'flop',
                          'turn', 'river').
            action (str): The action taken ('fold', 'call', 'raise').
            bet_size (float): The amount bet or raised.
            pot_size (float): The total pot size at the time of the action.

        Returns:
            bool: True if successful, False on error.
        """
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO user_poker_actions(
                        user_id,
                        round_number,
                        street,
                        action,
                        bet_size,
                        pot_size
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        round_number,
                        street,
                        action,
                        bet_size,
                        pot_size,
                    ),
                )
                return True

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error logging action for user {user_id}: {e}"
                )
                return False

    def get_unresolved_player_actions(self, user_id):
        """
        Retrieves all unresolved actions for a user, ordered by round number
        and creation time. Intended for use in crash recovery scenarios.

        Args:
            user_id (int): The user ID to retrieve unresolved actions for.

        Returns:
            list: A list of action dictionaries, or an empty list on error.
        """
        with self.connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        round_number,
                        street,
                        action,
                        bet_size,
                        pot_size,
                        created_at
                    FROM user_poker_actions
                    WHERE user_id = ?
                    AND resolved = 0
                    ORDER BY round_number ASC, created_at ASC
                """,
                    (user_id,),
                ).fetchall()

                return [dict(r) for r in rows]

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error getting unresolved actions for user {user_id}: {e}"
                )
                return []

    def resolve_player_actions(self, user_id: int, round_number: int) -> bool:
        """
        Marks all actions for a specific round as resolved by setting the
        resolved flag to 1.

        Args:
            user_id (int): The user ID whose actions will be resolved.
            round_number (int): The round number to mark as resolved.

        Returns:
            bool: True if successful, False on error.
        """
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    UPDATE user_poker_actions
                    SET resolved = 1
                    WHERE user_id = ?
                    AND round_number = ?
                """,
                    (user_id, round_number),
                )

                return True

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error resolving actions for user {user_id}, round {round_number}: {e}"
                )
                return False

    def update_hand_statistics(
        self,
        *,
        user_id,
        action,
        bet_size,
        pot_size,
        voluntarily_entered,
        preflop_raised,
        faced_raise,
    ):
        """
        Updates all aggregate poker statistics for a user after a hand
        completes.  Increments counters and recalculates VPIP/PFR.

        Args:
            user_id (int): The user ID to update.
            action (str): The final action taken ('fold', 'call', 'raise').
            bet_size (float): The amount bet during the hand.
            pot_size (float): The final pot size.
            voluntarily_entered (bool): Whether the player voluntarily put
                                        money in the pot (contributes to VPIP).
            preflop_raised (bool): Whether the player raised preflop
                                   (contributes to PFR).
            faced_raise (bool): Whether the player faced a raise during the
                                hand.

        Returns:
            bool: True if successful, False on error.
        """
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    UPDATE user_poker_data
                    SET
                        rounds_played = rounds_played + 1,
                        total_hands_played = total_hands_played + ?,
                        total_hands_raised = total_hands_raised + ?,
                        total_bets = total_bets + ?,
                        fold_to_raise = fold_to_raise + ?,
                        call_when_weak = call_when_weak + ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """,
                    (
                        int(voluntarily_entered),  # VPIP counter
                        int(preflop_raised),  # PFR counter
                        bet_size,  # Total bets
                        int(faced_raise and action == "fold"),  # Fold to raise
                        int(faced_raise and action == "call"),  # Call when weak
                        user_id,
                    ),
                )

                # Recalculate VPIP and PFR percentages
                self.recalculate_frequencies(conn, user_id)

                return True

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error updating hand statistics for user {user_id}: {e}"
                )
                return False

    def recalculate_frequencies(self, conn: sqlite3.Connection, user_id: int):
        """
        Recalculates and updates VPIP and PFR percentage values based on the
        current aggregate counters. Intended to be called internally after
        updating hand statistics.

        Args:
            conn (sqlite3.Connection): An active database connection to use.
            user_id (int): The user ID whose frequencies will be recalculated.
        """
        try:
            row = conn.execute(
                """
                SELECT
                    rounds_played,
                    total_hands_played,
                    total_hands_raised
                FROM user_poker_data
                WHERE user_id = ?
            """,
                (user_id,),
            ).fetchone()

            if not row or row["rounds_played"] == 0:
                return

            rounds = row["rounds_played"]
            vpip = (row["total_hands_played"] / rounds) * 100.0
            pfr = (row["total_hands_raised"] / rounds) * 100.0

            conn.execute(
                """
                UPDATE user_poker_data
                SET vpip = ?, pfr = ?
                WHERE user_id = ?
            """,
                (vpip, pfr, user_id),
            )

        except sqlite3.Error as e:
            database_logger.exception(
                f"Error recalculating frequencies for user {user_id}: {e}"
            )

    def get_player_statistics(self, user_id):
        """
        Retrieves summary poker statistics for a player, including derived
        statistics such as average bet size.

        Args:
            user_id (int): The user ID to retrieve statistics for.

        Returns:
            dict: Dictionary of statistics, or None if the user is not found
                  or an error occurs.
        """
        with self.connect() as conn:
            try:
                row = conn.execute(
                    """
                    SELECT
                        user_id,
                        rounds_played,
                        vpip,
                        pfr,
                        total_bets,
                        fold_to_raise,
                        call_when_weak
                    FROM user_poker_data
                    WHERE user_id = ?
                """,
                    (user_id,),
                ).fetchone()

                if not row:
                    return None

                stats = dict(row)

                # Calculate derived stats
                rounds = max(1, stats["rounds_played"])
                stats["avg_bet_size"] = stats["total_bets"] / rounds

                return stats

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error getting statistics for user {user_id}: {e}"
                )
                return None

    def get_hand_history(self, user_id, limit=50, resolved_only=True):
        """
        Retrieves recent hand action history for a player, optionally filtered
        to only resolved actions, ordered by most recent first.

        Args:
            user_id (int): The user ID to retrieve history for.
            limit (int): Maximum number of actions to return. Defaults to 50.
            resolved_only (bool): If True, only returns resolved actions.
                                  Defaults to True.

        Returns:
            list: A list of action dictionaries, or an empty list on error.
        """
        with self.connect() as conn:
            try:
                query = """
                    SELECT
                        round_number,
                        street,
                        action,
                        bet_size,
                        pot_size,
                        resolved,
                        created_at
                    FROM user_poker_actions
                    WHERE user_id = ?
                """

                if resolved_only:
                    query += " AND resolved = 1"

                query += " ORDER BY created_at DESC LIMIT ?"

                rows = conn.execute(query, (user_id, limit)).fetchall()

                return [dict(r) for r in rows]

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error getting hand history for user {user_id}: {e}"
                )
                return []

    def get_all_players_data(self):
        """
        Retrieves poker data for all players who have played at least one
        round. Useful for leaderboards and analytics. Calculates derived
        statistics (avg_bet_size) for each player.

        Returns:
            list: A list of player data dictionaries ordered by rounds played
                  descending, or an empty list on error.
        """
        with self.connect() as conn:
            try:
                rows = conn.execute("""
                    SELECT
                        user_id,
                        rounds_played,
                        vpip,
                        pfr,
                        total_bets
                    FROM user_poker_data
                    WHERE rounds_played > 0
                    ORDER BY rounds_played DESC
                """).fetchall()

                players = []
                for row in rows:
                    player = dict(row)
                    rounds = max(1, player["rounds_played"])
                    player["avg_bet_size"] = player["total_bets"] / rounds
                    players.append(player)

                return players

            except sqlite3.Error as e:
                database_logger.exception(f"Error getting all players data: {e}")
                return []

    def reset_player_statistics(self, user_id, keep_range=True):
        """
        Resets all poker statistics for a player to zero. Optionally preserves
        the player's stored range chart. Logs the reset to the database logger.

        Args:
            user_id (int): The user ID to reset.
            keep_range (bool): If True, the player_range is preserved.
                               Defaults to True.

        Returns:
            bool: True if successful, False on error.
        """
        with self.connect() as conn:
            try:
                if keep_range:
                    conn.execute(
                        """
                        UPDATE user_poker_data
                        SET
                            rounds_played = 0,
                            vpip = 0,
                            pfr = 0,
                            total_hands_played = 0,
                            total_hands_raised = 0,
                            total_bets = 0,
                            fold_to_raise = 0,
                            call_when_weak = 0,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """,
                        (user_id,),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE user_poker_data
                        SET
                            rounds_played = 0,
                            player_range = NULL,
                            vpip = 0,
                            pfr = 0,
                            total_hands_played = 0,
                            total_hands_raised = 0,
                            total_bets = 0,
                            fold_to_raise = 0,
                            call_when_weak = 0,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """,
                        (user_id,),
                    )

                database_logger.info(f"Reset statistics for user {user_id}")
                return True

            except sqlite3.Error as e:
                database_logger.exception(
                    f"Error resetting statistics for user {user_id}: {e}"
                )
                return False

    def get_special_mode_scores(self, user_id):
        """
        Retrieves the Gauntlet and Endless personal-best scores for a user.

        Args:
            user_id (int): The user ID to query.

        Returns:
            dict: Dictionary with keys ``gauntlet_max_rounds`` (int) and
                ``endless_high_score`` (int), or None if the user is not
                found or an error occurs.
        """
        with self.connect() as conn:
            try:
                row = conn.execute(
                    """
                    SELECT gauntlet_max_rounds, endless_high_score
                    FROM   user_poker_data
                    WHERE  user_id = ?
                    """,
                    (user_id,),
                ).fetchone()

                if not row:
                    database_logger.info(
                        f"No special-mode scores found for user_id {user_id}."
                    )
                    return None

                return {
                    "gauntlet_max_rounds": int(row["gauntlet_max_rounds"] or 0),
                    "endless_high_score": int(row["endless_high_score"] or 0),
                }

            except sqlite3.Error:
                database_logger.exception(
                    f"'get_special_mode_scores' error for user_id {user_id}."
                )
                return None

    def update_special_mode_score(self, user_id, column, new_score):
        """
        Updates a special-mode personal best only if ``new_score`` exceeds
        the currently stored value.  Uses a conditional UPDATE so the record
        is never downgraded (e.g. after a short run following a long one).

        Args:
            user_id  (int): The user ID to update.
            column   (str): Either ``"gauntlet_max_rounds"`` or
                            ``"endless_high_score"``.
            new_score (int): The candidate new personal best.

        Returns:
            bool: True if the update executed without error, False otherwise.

        Raises:
            ValueError: If ``column`` is not one of the two allowed values.
        """
        allowed = {"gauntlet_max_rounds", "endless_high_score"}
        if column not in allowed:
            raise ValueError(f"column must be one of {allowed}, got {column!r}")

        with self.connect() as conn:
            try:
                conn.execute(
                    f"""
                    UPDATE user_poker_data
                    SET {column} = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE  user_id      = ?
                    AND    {column}     < ?
                    """,
                    (new_score, user_id, new_score),
                )
                database_logger.info(
                    f"Updated {column} to {new_score} for user_id {user_id} "
                    f"(only applied if new_score > existing value)."
                )
                return True

            except sqlite3.Error:
                database_logger.exception(
                    f"'update_special_mode_score' error for user_id {user_id}."
                )
                return False


if __name__ == "__main__":
    dbm = DatabaseManagement()
    dbm.create_database()
