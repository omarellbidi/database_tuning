import pymysql
import time


conn = pymysql.connect(host="localhost",database="assignment_1_efficient",user="python_user", password="1234"      
)

cursor = conn.cursor()
#set time and rows
start_time = time.time()
rows_inserted = 0

print("Starting the straightforward upload to MariaDB...")


with open('/Users/omarellbidi/Desktop/UNI/Semster 6/Tuning  PS/blatt1 /dblp/auth.tsv', 'r', encoding='utf-8') as file:
    for line in file:
        columns = line.strip().split('\t')
        
        if len(columns) == 2:
            cursor.execute("INSERT INTO Auth (name, pubID) VALUES (%s, %s)", (columns[0], columns[1])
            )
            rows_inserted += 1

conn.commit()
cursor.close()
conn.close()

end_time = time.time()
print(f"Finished! Inserted {rows_inserted} rows.")
print(f"Total time taken: {end_time - start_time:.2f} seconds.")


