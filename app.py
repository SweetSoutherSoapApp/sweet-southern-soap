import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime

# --- 1. Google Sheets Authentication ---
# Update this to match the exact name of your new Google Sheet
SHEET_NAME = "Sweet Southern Soap Inventory" 

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
client = gspread.authorize(creds)

# Connect to the specific tabs in the spreadsheet
sheet = client.open(SHEET_NAME)
inventory_sheet = sheet.worksheet("Inventory")
customers_sheet = sheet.worksheet("Customers")

# Pull all current data
data = inventory_sheet.get_all_records()
customers_data = customers_sheet.get_all_records()
item_names = [str(item.get('Item Name', '')) for item in data]

# --- 2. Streamlit UI Dashboard Setup ---
st.set_page_config(page_title="Sweet Southern Soap", page_icon="🧼")
st.title("🧼 Sweet Southern Soap Dashboard")

tab1, tab2, tab3 = st.tabs(["Log Daily Sales", "Fix Errors / Restock", "Broadcast Emails"])

# --- TAB 1: Log Sales ---
with tab1:
    st.header("Log a Sale")
    selected_item = st.selectbox("What was sold?", item_names, key="sale_item")
    qty_sold = st.number_input("Quantity sold:", min_value=1, step=1, key="sale_qty")
    
    if st.button("Subtract from Inventory"):
        with st.spinner("Updating spreadsheet..."):
            # +2 accounts for 0-indexing in Python and the header row in Google Sheets
            row_index = item_names.index(selected_item) + 2
            current_qty = int(data[row_index - 2].get('Quantity Available', 0))
            new_qty = current_qty - qty_sold
            
            # NOTE: The '2' below assumes Quantity Available is in Column B. Update if it's in a different column!
            inventory_sheet.update_cell(row_index, 2, new_qty)
            st.success(f"Successfully subtracted {qty_sold} from {selected_item}. New total: {new_qty}")
            st.rerun()

# --- TAB 2: Restock ---
with tab2:
    st.header("Restock / Fix Errors")
    fix_item = st.selectbox("What are you restocking?", item_names, key="fix_item")
    restock_qty = st.number_input("Quantity to add:", min_value=1, step=1, key="restock_qty")
    
    if st.button("Add to Inventory"):
        with st.spinner("Updating spreadsheet..."):
            row_index = item_names.index(fix_item) + 2
            current_qty = int(data[row_index - 2].get('Quantity Available', 0))
            new_qty = current_qty + restock_qty
            
            # NOTE: The '2' below assumes Quantity Available is in Column B. Update if needed.
            inventory_sheet.update_cell(row_index, 2, new_qty)
            st.success(f"Successfully added {restock_qty} to {fix_item}! New total: {new_qty}")
            st.rerun()

# --- TAB 3: Broadcast Emails ---
with tab3:
    st.header("Broadcast Stock Email")
    st.write("Clicking this button will instantly email the current inventory to all selected customers.")
    
    if st.button("Send Email Blast Now"):
        with st.spinner("Compiling inventory and sending emails..."):
            
            # Filter inventory for items ready to ship with stock > 0
            available_items = [
                item for item in data 
                if str(item.get('Ready to Ship?', '')).strip().lower() == 'yes' and int(item.get('Quantity Available', 0)) > 0
            ]
            
            if not available_items:
                st.warning("Nothing to ship this week. Emails cancelled.")
            else:
                # Build the HTML inventory list
                inventory_list = "<ul>"
                for item in available_items:
                    inventory_list += f"<li><b>{item['Item Name']}</b>: {item['Quantity Available']} available at ${item['Price']}</li>"
                inventory_list += "</ul><p>Automated Email, please see contact info below to order. Thanks!</p>"
                
                # Generate unique timestamp to bypass Gmail "Show Quoted Text" hiding
                current_time = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p")
                
                # Replace with the real GitHub raw image URL once uploaded
                LOGOUT_URL = "URL_OF_YOUR_ONLINE_HOSTED_LOGO_IMAGE"
                
                # Branded Footer
                FOOTER_HTML = f"""
                    <div style="border-top: 2px solid #6b5b6b; padding-top: 15px; margin-top: 25px; font-family: sans-serif; text-align: center; color: #4a404a;">
                        <img src="{LOGOUT_URL}" alt="Sweet Southern Soap" style="max-width: 200px; width: 100%; height: auto; display: block; margin: 0 auto 10px auto;"><br>
                        <div style="margin-top: 5px;">
                            <strong>Marlin Johnson, Owner</strong><br>
                            <a href="mailto:sweetsouthernhoneyco@yahoo.com" style="color: #6b5b6b; text-decoration: none;">sweetsouthernhoneyco@yahoo.com</a><br>
                            <a href="tel:2512813131" style="color: #4a404a; text-decoration: none;">(251) 281-3131</a><br>
                            Sweet Southern Soap, Douglas and Diffee Rd, Grand Bay, AL, United States, 36541<br>
                            <a href="https://www.sweetsouthernsoap.com/" style="color: #6b5b6b; text-decoration: none;">www.sweetsouthernsoap.com</a><br>
                            <div style="margin-top: 10px; font-size: 0.9em;">
                                Follow us: | <a href="https://www.facebook.com/p/Sweet-Southern-Honey-Co-Sweet-Southern-Soap-61559107892303/" style="color: #6b5b6b; text-decoration: none;">Facebook @SweetSouthernHoneyCo&SweetSouthernSoap</a> | 
                            </div>
                        </div>
                        <div style="margin-top: 20px; font-size: 10px; color: #cccccc;">
                            Broadcast ID: {current_time}
                        </div>
                    </div>
                """
                
                # Authentication details
                SENDER_EMAIL = "app.sweetsouthernsoap@gmail.com"
                APP_PASSWORD = st.secrets["GMAIL_PASSWORD"]
                
                # Loop through customers and trigger emails based on 'Send?' column
                for customer in customers_data:
                    email = str(customer.get('Email Address', '')).strip()
                    customer_name = str(customer.get('Name', 'Friend')).strip()
                    send_status = str(customer.get('Send?', 'yes')).strip().lower()
                    
                    if not customer_name:
                        customer_name = "Friend"
                    
                    if email and send_status == 'yes':
                        # 1. Plain-text fallback for Spam Filters
                        plain_text = f"Hi {customer_name}, here is what's fresh this week at Sweet Southern Soap!\n\nAutomated Email, please see contact info below to order. Thanks!"
                        
                        # 2. HTML format 
                        personalized_html = f"<h2>Hi {customer_name}, here is what's fresh this week at Sweet Southern Soap!</h2>" + inventory_list + FOOTER_HTML
                        
                        msg = MIMEMultipart("alternative")
                        # Dynamic Subject Line prevents Gmail conversation threading
                        msg['Subject'] = f"Sweet Southern Soap: Fresh stock is ready! ({current_time})"
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = email
                        
                        # 3. Attach both elements (Plain text first)
                        msg.attach(MIMEText(plain_text, "plain"))
                        msg.attach(MIMEText(personalized_html, "html"))
                        
                        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                            server.login(SENDER_EMAIL, APP_PASSWORD)
                            server.sendmail(SENDER_EMAIL, email, msg.as_string())
                            
                st.success("Boom! Emails successfully sent to selected customers.")
