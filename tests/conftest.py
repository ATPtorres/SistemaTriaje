"""Configure the test process before importing the application's database."""
import os

# Every API test supplies its own session; never connect to the local MySQL server.
os.environ["DATABASE_URL"] = "sqlite://"
