import streamlit as st
import mysql.connector
import os
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
import re

# MySQL connection settings
MYSQL_HOST = "localhost"
MYSQL_USER = "food"  # Replace with your MySQL username
MYSQL_PASSWORD = "Ronu@2002"  # Replace with your MySQL password
MYSQL_DATABASE = "employee_page"  # Replace with your database name

# Folder to store uploaded documents
DOCUMENT_UPLOAD_FOLDER = "uploaded_documents"
os.makedirs(DOCUMENT_UPLOAD_FOLDER, exist_ok=True)

# Establish a connection to MySQL
def connect_to_mysql():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

# Function to load employee data from MySQL
def load_employee_data():
    connection = connect_to_mysql()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    connection.close()
    return employees

# Function to load all existing IDs from MySQL
def load_existing_ids():
    connection = connect_to_mysql()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM employees")
    ids = [row[0] for row in cursor.fetchall()]
    connection.close()
    return ids

# Function to save unmatched document ID to MySQL
def save_unmatched_id_to_mysql(document_id):
    connection = connect_to_mysql()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO unmatched_ids (document_id) VALUES (%s)", (document_id,)
    )
    connection.commit()
    connection.close()

# Function to extract ID from document content
def extract_id_from_content(content):
    match = re.search(r"ID:\s*(\d+)", content)
    return match.group(1) if match else None

# Function to read content of the uploaded documents
def read_document_content(file_path, file_name):
    try:
        if file_name.endswith(".pdf"):
            reader = PdfReader(file_path)
            return " ".join(page.extract_text() for page in reader.pages)
        elif file_name.lower().endswith((".jpg", ".png")):
            image = Image.open(file_path)
            return pytesseract.image_to_string(image)
        elif file_name.endswith(".txt"):
            with open(file_path, "r") as f:
                return f.read()
        else:
            return "Unsupported file format."
    except Exception as e:
        return f"Error reading content: {str(e)}"

# Function to handle file uploads
def handle_file_upload(employee_id, uploaded_files):
    existing_ids = load_existing_ids()

    for uploaded_file in uploaded_files:
        file_name = f"{employee_id}_{uploaded_file.name}"
        file_path = os.path.join(DOCUMENT_UPLOAD_FOLDER, file_name)
        with open(file_path, "wb") as f:
            file_data = uploaded_file.read()
            f.write(file_data)

        content = read_document_content(file_path, uploaded_file.name)
        st.text_area(f"Content of {uploaded_file.name}:", content, height=200)

        document_id = extract_id_from_content(content)
        if document_id:
            if int(document_id) not in existing_ids:
                save_unmatched_id_to_mysql(document_id)
                st.warning(f"Unmatched Document ID found: {document_id}. Saved to database.")

# Add new employee functionality
def add_new_employee():
    st.subheader("Add New Employee")
    with st.form("add_employee_form"):
        name = st.text_input("Employee Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number")

        submit_employee = st.form_submit_button("Add Employee")
        if submit_employee:
            if name and email and phone:
                connection = connect_to_mysql()
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO employees (name, email, phone) VALUES (%s, %s, %s)",
                    (name, email, phone),
                )
                connection.commit()
                connection.close()
                st.success(f"Employee {name} has been added.")
            else:
                st.error("Please fill in all required fields.")

# Add document functionality
def add_document(employee_data):
    st.subheader("Add Document for Employee")
    with st.form("add_document_form"):
        employee_id = st.selectbox("Select Employee ID", [emp["id"] for emp in employee_data], format_func=lambda x: f"ID: {x}")
        uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True)
        submit_documents = st.form_submit_button("Upload Documents")
        if submit_documents:
            if employee_id and uploaded_files:
                handle_file_upload(employee_id, uploaded_files)
                st.success(f"Uploaded {len(uploaded_files)} document(s) for Employee ID {employee_id}.")
            else:
                st.error("Please select an employee and upload at least one document.")

# Dashboard interface
def dashboard():
    st.title("Employee Dashboard")
    st.sidebar.title("Menu")

    # Sidebar menu for navigation
    menu = st.sidebar.radio(
        "Choose an option:",
        ("View Employees", "Add New Employee", "Add Document"),
    )

    employee_data = load_employee_data()

    # Display based on selected menu
    if menu == "View Employees":
        st.subheader("Employee Details")
        if employee_data:
            for emp in employee_data:
                st.write(f"### Employee: {emp['name']}")
                st.write(f"*Email:* {emp['email']}")
                st.write(f"*Phone:* {emp['phone']}")
                st.write(f"*Employee ID:* {emp['id']}")
        else:
            st.write("No employees found.")
    elif menu == "Add New Employee":
        add_new_employee()
    elif menu == "Add Document":
        add_document(employee_data)

if __name__ == "__main__":
    dashboard()
