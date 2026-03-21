import pymysql
import time


conn = pymysql.connect(
    host="localhost",
    database="assignment_1_efficient",
    user="python_user",
    password="1234",
    local_infile=True 
)

cursor = conn.cursor()

print("Emptying the old data")
cursor.execute("TRUNCATE TABLE Auth;")
conn.commit()

print("Starting the EFFICIENT upload to MariaDB...")
start_time = time.time()


file_path = '/Users/omarellbidi/Desktop/UNI/Semster 6/Tuning  PS/blatt1 /dblp/auth.tsv'

load_query = f"""
LOAD DATA LOCAL INFILE '{file_path}'
INTO TABLE Auth
FIELDS TERMINATED BY '\\t'
LINES TERMINATED BY '\\n'
(name, pubID);
"""

cursor.execute(load_query)
conn.commit()

cursor.close()
conn.close()

end_time = time.time()
print(f"Finished EFFICIENT MariaDB upload")
print(f"Total time taken: {end_time - start_time:.2f} seconds.")
