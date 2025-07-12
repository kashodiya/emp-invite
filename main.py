from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import aiosqlite
from datetime import datetime
from typing import Optional, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from jinja2 import Environment, BaseLoader

load_dotenv()

# Read environment variables
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')

with open("email-template.txt", "r") as f:
    email_template = f.read().strip()

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="client"), name="static")

class EmployeeUpdate(BaseModel):
    email_invite_sent: Optional[bool] = None
    reply_received: Optional[bool] = None
    wants_to_participate: Optional[bool] = None
    phone_number: Optional[str] = None
    comments: Optional[str] = None

class BulkEmailRequest(BaseModel):
    emails: List[str] 
 
@app.get("/")
async def read_root():
    print("Serving index.html")
    return FileResponse("client/index.html")

@app.get("/api/employees")
async def get_employees():
    print("Fetching all employees")
    async with aiosqlite.connect("employee_database.db") as db:
        cursor = await db.execute("SELECT rowid, * FROM employees WHERE isHindu = 'Yes'")
        # cursor = await db.execute("SELECT rowid, * FROM employees")
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        employees = [dict(zip(columns, row)) for row in rows]
        print(f"Found {len(employees)} employees")
        return employees

@app.put("/api/employees/{employee_id}")
async def update_employee(employee_id: int, update: EmployeeUpdate):
    print(f"Updating employee {employee_id} with data: {update.model_dump()}")
    
    async with aiosqlite.connect("employee_database.db") as db:
        updates = []
        values = []
        
        if update.email_invite_sent is not None:
            updates.append("email_invite_sent = ?")
            values.append(1 if update.email_invite_sent else 0)
            if update.email_invite_sent:
                updates.append("email_sent_at = ?")
                values.append(datetime.now().isoformat())
                print(f"Email sent timestamp recorded for employee {employee_id}")
        
        if update.reply_received is not None:
            updates.append("reply_received = ?")
            values.append(1 if update.reply_received else 0)
            if update.reply_received:
                updates.append("email_replied_at = ?")
                values.append(datetime.now().isoformat())
                print(f"Email reply timestamp recorded for employee {employee_id}")
        
        if update.wants_to_participate is not None:
            updates.append("wants_to_participate = ?")
            values.append(1 if update.wants_to_participate else 0)
        
        if update.phone_number is not None:
            updates.append("phone_number = ?")
            values.append(update.phone_number)
        
        if update.comments is not None:
            updates.append("comments = ?")
            values.append(update.comments)
        
        if updates:
            values.append(employee_id)
            query = f"UPDATE employees SET {', '.join(updates)} WHERE rowid = ?"
            print(f"Executing query: {query} with values: {values}")
            cursor = await db.execute(query, values)
            await db.commit()
            print(f"Employee {employee_id} updated successfully, rows affected: {cursor.rowcount}")
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Employee not found")
        
        return {"message": "Employee updated successfully"}

@app.get("/api/employees/{employee_id}")
async def get_employee(employee_id: int):
    async with aiosqlite.connect("employee_database.db") as db:
        cursor = await db.execute("SELECT rowid, * FROM employees WHERE rowid = ?", (employee_id,))
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        raise HTTPException(status_code=404, detail="Employee not found")


# Defining the prepare_email() method
def prepare_email(full_name, email):
    print(f"Sending email to {full_name} ({email})")
    
    env = Environment(loader=BaseLoader)
    template = env.from_string(email_template)
    email_body = template.render({"name": full_name})

    # print(email_body)

    return email_body

@app.post("/api/send-emails")
async def send_bulk_emails(request: BulkEmailRequest):
    async with aiosqlite.connect("employee_database.db") as db:
        placeholders = ','.join('?' * len(request.emails))
        cursor = await db.execute(f"SELECT email, highlightedName FROM employees WHERE email IN ({placeholders})", request.emails)
        employees = await cursor.fetchall()
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        
        sent_count = 0
        for email, highlighted_name in employees:
            try:
                # Send actual email via SMTP
                msg = MIMEMultipart()
                msg['From'] = SENDER_EMAIL
                # msg['To'] = SENDER_EMAIL
                msg['To'] = email
                msg['Subject'] = "Personal Invitation - Community Opportunity (Optional)"
                body = prepare_email(highlighted_name, email)
                msg.attach(MIMEText(body, 'plain'))

                # send_email(server, sender, receiver, subject, body)
                server.send_message(msg)
                
                print(f"Email sent to {highlighted_name} ({email})")
                
                # Update email_invite_sent status
                await db.execute("UPDATE employees SET email_invite_sent = 1, email_sent_at = ? WHERE email = ?", 
                                (datetime.now().isoformat(), email))
                sent_count += 1
            except Exception as e:
                print(f"Failed to send email to {email}: {e}")

        server.quit()
        await db.commit()
        return {"message": f"Emails sent to {sent_count} employees"}

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)