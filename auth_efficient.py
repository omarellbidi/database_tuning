import psycopg2
import time


conn = psycopg2.connect(host="localhost", database="postgres", user="omarellbidi", password="")
cursor = conn.cursor()

# Empty the PostgreSQL filing cabinet 
print("Emptying the old data")
cursor.execute("TRUNCATE TABLE Auth;")
conn.commit()

print("Starting the EFFICIENT upload using COPY...")
start_time = time.time()


file = '/Users/omarellbidi/Desktop/UNI/Semster 6/Tuning  PS/blatt1 /dblp/auth.tsv'
with open(file, 'r', encoding='utf-8') as file:
    # streaming the file directly into the table
    cursor.copy_from(file, 'auth', sep='\t')

conn.commit()
cursor.close()
conn.close()

end_time = time.time()
print(f"Finished EFFICIENT upload!")
print(f"Total time taken: {end_time - start_time:.2f} seconds.")

