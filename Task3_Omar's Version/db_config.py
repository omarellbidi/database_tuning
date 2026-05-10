# db_config.py
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="postgres",
        user="kitajimamitsuhiro",
        password="" 
    )
