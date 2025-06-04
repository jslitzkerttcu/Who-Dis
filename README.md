# 🕵️‍♂️ WhoDis - Identity Lookup with Attitude

A Flask-based identity lookup tool for IT teams who are tired of clicking through five admin portals to find a phone number. Includes RBAC, Azure AD integration, and denial messages that slap.

---

## 🤔 What Even Is This?

**WhoDis** is a secure(ish) internal web tool for finding out *who the heck someone is* based on name, email, username, or phone number.
It authenticates via Azure AD (or fallback basic auth if you’re feeling retro), and includes role-based access so not everyone can break things.
Best of all? Denied access results in a full-screen “NOPE.” because dignity is overrated.

---

## 🔐 Roles, Because Power Should Be Tiered

* 👀 **Viewers**: Can search. Can’t break stuff.
* 🛠 **Editors**: Can break stuff. (Coming soon.)
* 👑 **Admins**: Own the console. And the consequences.

---

## 🧠 Key Features

* 🔒 **Role-Based Access Control** (RBAC): Three levels of permissions, zero room for error.
* 🎭 **Azure AD Integration**: Because we like single sign-on more than you.
* 🪵 **Access Denial Logging**: Every failed attempt is logged *and* ridiculed.
* 🎨 **Bootstrap UI**: Because your eyes deserve better than raw HTML.
* 🧱 **Modular Flask Blueprints**: Yes, we’ve heard of architecture.

---

## 🛠 Tech Stack (a.k.a. The Nerd Stuff)

| Layer      | Tool             |
| ---------- | ---------------- |
| Backend    | Flask 3.0.0      |
| Frontend   | Bootstrap 5.3.0  |
| Auth       | Azure AD / Basic |
| Templating | Jinja2           |
| Secrets    | `python-dotenv`  |

---

## 🚀 Quickstart

1. Clone the repo like a boss:

   ```bash
   git clone https://github.com/jslitzkerttcu/Who-Dis.git
   cd Who-Dis
   ```

2. Fire up a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Or venv\Scripts\activate if you're stuck on Windows
   ```

3. Install the magic:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure your `.env` like a responsible adult:

   ```env
   FLASK_HOST=0.0.0.0
   FLASK_PORT=5000
   FLASK_DEBUG=True
   SECRET_KEY=your-very-secret-key
   VIEWERS=viewer@example.com
   EDITORS=editor@example.com
   ADMINS=admin@example.com
   ```

5. Run it like it owes you money:

   ```bash
   python run.py
   ```

> You’ll find it judging your access attempts at [http://localhost:5000](http://localhost:5000)

---

## 🗂 Project Layout

```
WhoDis/
├── app/                # All the brains
│   ├── blueprints/     # Modular chunks of logic
│   │   ├── admin/      # Admin-only secrets
│   │   ├── home/       # The welcome mat
│   │   └── search/     # Lookup logic
│   ├── middleware/     # Auth, because trust issues
│   └── templates/      # The visual lies we tell users
├── static/             # CSS and JS wizardry
├── logs/               # We saw what you did
├── run.py              # Launch codes
└── requirements.txt    # Feed this to pip
```

---

## 🛡 Authentication: The Gatekeeper

* **Azure AD**: Checks the `X-MS-CLIENT-PRINCIPAL-NAME` header to see who dares approach.
* **Basic Auth**: For devs and rebels working without SSO.

💡 Whitelisted users only. No whitelist, no entry. Not sorry.

---

## 🚨 Security Notes

* Change the `SECRET_KEY` unless you like living dangerously
* Logs unauthorized access attempts because we're petty like that
* Never commit your `.env` unless you’re trying to get fired

---

## 📈 Current MVP Status

* ✅ Auth system (you’ll be denied *beautifully*)
* ✅ Role-based access
* ✅ Logs for shame
* ✅ The UI doesn’t suck
* ⏳ Search logic coming soon (we promise)
* ⏳ Editor tools pending imagination
* ⏳ DB integration once we trust it with state

---

## 🧑‍💻 Contributing

Got ideas? Found a bug? Want to make the denial messages even more savage? Fork it. PR it. Flex it.

---

## ⚖ License

\[Insert serious license stuff here]

---

## 🤘 Made By

The TTCU Dev Team — giving internal tools the sarcasm they deserve.

---

Let me know if you want it converted directly into the `README.md` file format with collapsible sections, emojis removed for terminals, or a badge section for added ✨ fake professionalism ✨.
