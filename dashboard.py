import streamlit as st
import mysql.connector
import os
from PyPDF2 import PdfReader, PdfWriter
import hashlib
import re

# MySQL connection settings
MYSQL_HOST = "localhost"
MYSQL_USER = "food"  # Replace with your MySQL username
MYSQL_PASSWORD = "Ronu@2002"  # Replace with your MySQL password
MYSQL_DATABASE = "employee_page"  # Replace with your database name

# Folder to store uploaded documents
DOCUMENT_UPLOAD_FOLDER = "uploaded_documents"
os.makedirs(DOCUMENT_UPLOAD_FOLDER, exist_ok=True)

MAX_UPLOAD_SIZE_MB = 5  # Maximum upload size in MB

# Establish a connection to MySQL
def connect_to_mysql():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

# Function to load document hashes from MySQL
def load_invoice_hashes():
    connection = connect_to_mysql()
    cursor = connection.cursor()
    cursor.execute("SELECT invoice_hash FROM invoices")
    hashes = {row[0] for row in cursor.fetchall()}
    connection.close()
    return hashes

# Function to calculate hash of a given content
def calculate_hash(content):
    return hashlib.sha256(content.encode()).hexdigest()

# Function to repair a corrupted PDF
def repair_pdf(file_path):
    """Attempts to repair a corrupted PDF file."""
    try:
        with open(file_path, "rb") as infile:
            reader = PdfReader(infile)
            repaired_pdf_path = file_path.replace(".pdf", "_repaired.pdf")
            with open(repaired_pdf_path, "wb") as outfile:
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                writer.write(outfile)
            return repaired_pdf_path
    except Exception as e:
        return None

# Function to extract text from a PDF
def extract_text_from_pdf(file_path):
    """Extracts text from a PDF, skipping corrupted pages if any."""
    try:
        content = []
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for i, page in enumerate(reader.pages):
                try:
                    content.append(page.extract_text())
                except Exception as e:
                    st.warning(f"Could not read page {i + 1}: {str(e)}")
        return " ".join(content)
    except Exception as e:
        return None

# Function to extract individual invoices from a PDF
def extract_invoices_from_pdf(file_path):
    # Repair the PDF first if needed
    repaired_pdf_path = repair_pdf(file_path)
    pdf_path_to_read = repaired_pdf_path if repaired_pdf_path else file_path

    # Extract text, skipping corrupted pages
    content = extract_text_from_pdf(pdf_path_to_read)
    if not content:
        return []

    # Split invoices by a keyword, e.g., "Invoice No:"
    invoices = re.split(r"(Invoice No:\s*\d+)", content, flags=re.IGNORECASE)
    combined_invoices = []

    for i in range(1, len(invoices), 2):
        invoice_header = invoices[i]
        invoice_body = invoices[i + 1] if i + 1 < len(invoices) else ""
        combined_invoices.append(invoice_header + invoice_body)

    return combined_invoices

def handle_file_upload(employee_id, employee_name, uploaded_files):
    existing_hashes = load_invoice_hashes()

    for uploaded_file in uploaded_files:
        file_size_mb = len(uploaded_file.read()) / (1024 * 1024)
        uploaded_file.seek(0)  # Reset file pointer

        if file_size_mb > MAX_UPLOAD_SIZE_MB:
            st.error(f"File {uploaded_file.name} exceeds the size limit of {MAX_UPLOAD_SIZE_MB} MB.")
            continue

        # Save file temporarily for processing
        file_name = f"{employee_id}_{uploaded_file.name}"
        file_path = os.path.join(DOCUMENT_UPLOAD_FOLDER, file_name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())

        # Extract invoices and calculate hashes
        invoices = extract_invoices_from_pdf(file_path)
        if len(invoices) > 6:
            st.warning(f"File {uploaded_file.name} contains more than 6 invoices. Processing...")
        duplicate_count = 0
        new_count = 0

        for invoice in invoices:
            invoice_hash = calculate_hash(invoice)

            # Check if hash already exists and by whom
            connection = connect_to_mysql()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT employee_id, employee_name 
                FROM invoices 
                WHERE invoice_hash = %s
                """,
                (invoice_hash,),
            )
            result = cursor.fetchone()
            connection.close()

            if result:  # Invoice hash found
                if str(result["employee_id"]) == str(employee_id):
                    st.warning(f"Duplicate Invoice Detected for Employee ID {employee_id}: {invoice[:50]}...")
                else:
                    st.error(
                        f"Invoice already uploaded by another employee "
                        f"({result['employee_name']} - Employee ID: {result['employee_id']}): {invoice[:50]}..."
                    )
                duplicate_count += 1
            else:  # New invoice, save to database
                connection = connect_to_mysql()
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO invoices (employee_id, employee_name, invoice_hash) 
                    VALUES (%s, %s, %s)
                    """,
                    (employee_id, employee_name, invoice_hash),
                )
                connection.commit()
                connection.close()

                st.success(f"New Invoice Processed: {invoice[:50]}...")
                new_count += 1

        st.info(f"Processed {len(invoices)} invoices: {new_count} new, {duplicate_count} duplicates.")
# Add document functionality
def add_document(employee_data):
    st.subheader("Add Document for Employee")
    with st.form("add_document_form"):
        selected_employee = st.selectbox(
            "Select Employee",
            employee_data,
            format_func=lambda emp: f"{emp['name']} (ID: {emp['id']})",
        )
        uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True, type=["pdf","jpg"])
        submit_documents = st.form_submit_button("Upload Documents")
        if submit_documents:
            if selected_employee and uploaded_files:
                employee_id = selected_employee["id"]
                employee_name = selected_employee["name"]
                handle_file_upload(employee_id, employee_name, uploaded_files)
            else:
                st.error("Please select an employee and upload at least one document.")

# Load employee data from MySQL
def load_employee_data():
    connection = connect_to_mysql()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    connection.close()
    return employees

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
                st.write(f"Email: {emp['email']}")
                st.write(f"Phone: {emp['phone']}")
                st.write(f"Employee ID: {emp['id']}")
        else:
            st.write("No employees found.")
    elif menu == "Add New Employee":
        add_new_employee()
    elif menu == "Add Document":
        add_document(employee_data)

if __name__ == "__main__":
    dashboard()
