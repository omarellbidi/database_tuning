# db_config.py
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="",
        database="",
        user="",
        password="" 
    )
