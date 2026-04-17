"""
Fill the database with 100k employees, 100k students, and 10 technical departments.
Only about 10% of the employees are in a technical department. 
To avoid collision, we use (offset + index) to generate ssnum.
"""
import pandas as pd
import random


TECH_DEPARTMENTS = ["Tech1", "Tech2", "Tech3", "Tech4", "Tech5", "Tech6", "Tech7", "Tech8", "Tech9", "Tech10"]
NON_TECH_DEPARTMENTS = ["NonTech1", "NonTech2", "NonTech3", "NonTech4", "NonTech5", "NonTech6", "NonTech7", "NonTech8", "NonTech9", "NonTech10"]
COURSES = ["Course1", "Course2", "Course3", "Course4", "Course5", "Course6", "Course7", "Course8", "Course9", "Course10"]
MANAGERS=["Manager1", "Manager2", "Manager3", "Manager4", "Manager5", "Manager6", "Manager7"]
LOCATIONS=["Location1", "Location2", "Location3", "Location4", "Location5"]

EMPLOYEE_OFFSET = 100_000
STUDENT_OFFSET = 200_000


def populate_tsv(num_students=100_000, num_employees=100_000, num_techdepts=10) -> None:
    employee_header = ["ssnum","name","manager","dept","salary","numfriends"]
    student_header = ["ssnum","name","course","grade"]
    techdept_header = ["dept","manager","location"]

    student_data = []
    employee_data = []
    techdept_data = []

    print("writing employee data...")
    for i in range(num_employees):
        add_employee_row(employee_data, i)
    
    print("writing student data...")
    for i in range(num_students):
        add_student_row(student_data, i)

    print("writing techdept data...")
    for i in range(num_techdepts):
        add_techdept_row(techdept_data, i)

    print("writing data to tsv files...")
    student_df = pd.DataFrame(columns=student_header, data=student_data)
    employee_df = pd.DataFrame(columns=employee_header, data=employee_data)
    techdept_df = pd.DataFrame(columns=techdept_header, data=techdept_data)
    student_df.to_csv("data/student.tsv", sep="\t", index=False)
    employee_df.to_csv("data/employee.tsv", sep="\t", index=False)
    techdept_df.to_csv("data/techdept.tsv", sep="\t", index=False)

    print("done")

    
def add_employee_row(data: list, i: int) -> None:
    """
    Add a row to the employee data.
    Only about 10% of the employees are in a technical department. 
    """
    ssnum = i + EMPLOYEE_OFFSET
    name = "Employee" + str(i)
    manager = random.choice(MANAGERS)
    rd = random.random() < 0.1
    dept = random.choice(TECH_DEPARTMENTS) if rd else random.choice(NON_TECH_DEPARTMENTS)
    salary = random.randrange(50000, 1500001, 1000)
    numfriends = random.randint(0, 20)
    data.append([ssnum, name, manager, dept, salary, numfriends])


def add_student_row(data: list, i: int) -> None:
    ssnum = i + STUDENT_OFFSET
    name = "Student" + str(i)
    course = random.choice(COURSES)
    grade = random.randint(10, 50) / 10 # [1.0, 1.1, ..., 4.9, 5.0]
    data.append([ssnum, name, course, grade])


def add_techdept_row(data: list, i: int) -> None:
    """
    Add a row to the techdept data with following constraints:
    - A manager may manage multiple departments
    - A location may contain multiple departments
    """
    dept = TECH_DEPARTMENTS[i]
    # While there are 10 technical departments, 
    # there are only 7 managers and 5 locations.
    # so there should be duplicate choices.
    manager = random.choice(MANAGERS)
    location = random.choice(LOCATIONS)
    data.append([dept, manager, location])


if __name__ == "__main__":
    populate_tsv()
