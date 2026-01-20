# 🔑 Institute KeyHub (Asset Management System)

A web-based Asset Management System designed for institutes to manage room keys and equipment. It features QR code scanning for borrowing/returning items, role-based access control (Admin/User), and PWA capabilities for mobile installation.

## 🚀 Features

* **Role-Based Access:**
    * **Admins:** Manage inventory, approve users, scan QR codes, view audit logs.
    * **Staff/Students:** Browse available keys, book items, generate QR codes for pickup.
* **Smart Inventory:**
    * Track **Keys** (with floor levels) and **Equipment** (laptops, projectors).
    * **Batch Processing:** Add or delete hundreds of items at once using CSV templates.
* **QR Code Workflow:**
    * Users get a digital "ticket" (QR Code) when booking.
    * Admins scan the QR code to instantly approve pickup or return.
* **Audit Logs:** tracks every action (Pickup, Return, Manual Override) with timestamps.
* **Mobile Ready (PWA):** Can be installed on phones as an app; works offline for basic navigation.

## 🛠️ Tech Stack

* **Backend:** Python (Flask), SQLAlchemy
* **Frontend:** HTML5, Bootstrap 5, Jinja2
* **Database:** SQLite (Local) / PostgreSQL (Production)
* **Deployment:** Docker / Render

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/KeyHub.git](https://github.com/YOUR_USERNAME/KeyHub.git)
cd KeyHub