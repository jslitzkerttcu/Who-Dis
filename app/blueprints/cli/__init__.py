from flask import Blueprint, render_template, jsonify, request
from app.middleware.auth import require_role

cli_bp = Blueprint("cli", __name__)


@cli_bp.route("/")
@require_role("viewer")
def terminal():
    """Display the CLI terminal interface."""
    return render_template("cli/terminal.html")


@cli_bp.route("/execute", methods=["POST"])
@require_role("viewer")
def execute_command():
    """Execute a CLI command and return results."""
    command = request.json.get("command", "").strip()

    if not command:
        return jsonify(
            {"success": False, "output": "Error: No command provided", "type": "error"}
        )

    # Parse command
    parts = command.split()
    if not parts:
        return jsonify(
            {"success": False, "output": "Error: Invalid command", "type": "error"}
        )

    cmd = parts[0].lower()

    # Handle commands
    if cmd == "help":
        return jsonify({"success": True, "output": get_help_text(), "type": "help"})

    elif cmd == "whois":
        if len(parts) < 2:
            return jsonify(
                {
                    "success": False,
                    "output": "Error: whois requires a username or email\nUsage: whois <username|email>",
                    "type": "error",
                }
            )

        search_term = " ".join(parts[1:])
        return execute_whois(search_term)

    elif cmd == "clear":
        return jsonify({"success": True, "output": "", "type": "clear"})

    elif cmd == "whoami":
        user_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        user_role = getattr(request, "user_role", "viewer")
        return jsonify(
            {
                "success": True,
                "output": f"Current user: {user_email}\nRole: {user_role}",
                "type": "info",
            }
        )

    elif cmd == "hack":
        if len(parts) > 1 and parts[1].lower() == "the":
            if len(parts) > 2 and parts[2].lower() == "planet":
                return hack_the_planet()
            elif len(parts) > 2 and parts[2].lower() == "gibson":
                return hack_the_gibson()
        return jsonify(
            {
                "success": True,
                "output": "Usage: hack the planet | hack the gibson\n\nRemember: Hack the planet!",
                "type": "info",
            }
        )

    elif cmd == "matrix":
        return show_matrix()

    elif cmd == "ping":
        if len(parts) > 1:
            target = parts[1]
            return ping_target(target)
        return jsonify(
            {"success": False, "output": "Usage: ping <target>", "type": "error"}
        )

    elif cmd == "sudo":
        if len(parts) > 1 and " ".join(parts[1:3]) == "make me":
            if len(parts) > 3 and parts[3] == "sandwich":
                return make_sandwich()
        return jsonify(
            {
                "success": True,
                "output": "[sudo] password for user: \nNice try, but I'm not falling for that!",
                "type": "info",
            }
        )

    elif cmd == "uptime":
        return show_uptime()

    elif cmd == "fortune":
        return show_fortune()

    else:
        return jsonify(
            {
                "success": False,
                "output": f"bash: {cmd}: command not found\nType 'help' for available commands",
                "type": "error",
            }
        )


def get_help_text():
    """Return help text for the CLI."""
    return """WhoDis Terminal v1.0
    
Available commands:
  whois <username|email>  - Search for user identity
  whoami                  - Display current user info
  clear                   - Clear terminal screen
  help                    - Show this help message
  
Fun commands:
  hack the planet         - Channel your inner Zero Cool
  hack the gibson         - Access the Gibson supercomputer
  matrix                  - Enter the Matrix
  ping <target>           - Ping a target (harmlessly)
  sudo make me sandwich   - Request elevated sandwich privileges
  uptime                  - Show system uptime
  fortune                 - Get your hacker fortune
  
Examples:
  whois john.doe
  whois jdoe@example.com
  hack the planet
  matrix
"""


def execute_whois(search_term):
    """Execute whois command by searching for user."""
    try:
        # Import services
        from app.services.ldap_service import ldap_service
        from app.services.genesys_service import genesys_service
        from app.services.graph_service import graph_service
        from concurrent.futures import ThreadPoolExecutor

        # Search timeout
        SEARCH_TIMEOUT = 15

        ldap_result = None
        genesys_result = None
        graph_result = None

        # Search concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            ldap_future = executor.submit(ldap_service.search_user, search_term)
            genesys_future = executor.submit(genesys_service.search_user, search_term)
            graph_future = executor.submit(
                graph_service.search_user, search_term, False
            )

            # Get LDAP results
            try:
                ldap_data = ldap_future.result(timeout=SEARCH_TIMEOUT)
                if ldap_data:
                    if isinstance(ldap_data, list):
                        ldap_result = ldap_data[0] if ldap_data else None
                    else:
                        ldap_result = ldap_data
            except Exception:
                ldap_result = None

            # Get Genesys results
            try:
                genesys_data = genesys_future.result(timeout=SEARCH_TIMEOUT)
                if genesys_data:
                    if isinstance(genesys_data, list):
                        genesys_result = genesys_data[0] if genesys_data else None
                    else:
                        genesys_result = genesys_data
            except Exception:
                genesys_result = None

            # Get Graph results
            try:
                graph_data = graph_future.result(timeout=SEARCH_TIMEOUT)
                if graph_data:
                    if isinstance(graph_data, list):
                        graph_result = graph_data[0] if graph_data else None
                    else:
                        graph_result = graph_data
            except Exception:
                graph_result = None

        # Merge LDAP and Graph data for Azure AD
        azureAD_result = None
        if ldap_result or graph_result:
            from app.blueprints.search import merge_ldap_graph_data

            azureAD_result = merge_ldap_graph_data(
                ldap_result, graph_result, include_photo=False
            )

        result = {"azureAD": azureAD_result, "genesys": genesys_result}

        if result is None:
            return jsonify(
                {
                    "success": True,
                    "output": f"whois: {search_term}: No results found",
                    "type": "info",
                }
            )

        # Format the results in CLI style
        output = format_cli_results(search_term, result)

        return jsonify(
            {
                "success": True,
                "output": output,
                "type": "result",
                "data": result,  # Include raw data for potential formatting
            }
        )

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "output": f"whois: Error searching for '{search_term}': {str(e)}",
                "type": "error",
            }
        )


def format_cli_results(search_term, result):
    """Format search results in CLI style."""
    output = []
    output.append(f"=== WHOIS LOOKUP: {search_term} ===\n")

    # Azure AD Results
    if result.get("azureAD"):
        user = result["azureAD"]
        output.append("[AZURE AD/LDAP]")
        output.append("-" * 40)

        if user.get("displayName"):
            output.append(f"Name:           {user['displayName']}")
        if user.get("mail"):
            output.append(f"Email:          {user['mail']}")
        if user.get("sAMAccountName"):
            output.append(f"Username:       {user['sAMAccountName']}")
        if user.get("employeeID"):
            output.append(f"Employee ID:    {user['employeeID']}")
        if user.get("department"):
            output.append(f"Department:     {user['department']}")
        if user.get("title"):
            output.append(f"Title:          {user['title']}")
        if user.get("manager"):
            output.append(f"Manager:        {user['manager']}")

        # Status
        if user.get("enabled") is not None:
            status = "Enabled" if user["enabled"] else "Disabled"
            locked = " [LOCKED]" if user.get("locked") else ""
            output.append(f"Status:         {status}{locked}")

        # Phone numbers
        phones = user.get("phoneNumbers", {})
        if phones:
            output.append("Phone Numbers:")
            for phone_type, number in phones.items():
                output.append(f"  {phone_type.capitalize()}: {number}")

        output.append("")

    # Genesys Results
    if result.get("genesys"):
        user = result["genesys"]
        output.append("[GENESYS CLOUD]")
        output.append("-" * 40)

        if user.get("name"):
            output.append(f"Name:           {user['name']}")
        if user.get("email"):
            output.append(f"Email:          {user['email']}")
        if user.get("username"):
            output.append(f"Username:       {user['username']}")
        if user.get("department"):
            output.append(f"Department:     {user['department']}")
        if user.get("title"):
            output.append(f"Title:          {user['title']}")
        if user.get("state"):
            output.append(f"State:          {user['state']}")

        # Skills
        if user.get("skills"):
            output.append(f"Skills:         {', '.join(user['skills'][:3])}")
            if len(user["skills"]) > 3:
                output.append(f"                ... and {len(user['skills']) - 3} more")

        # Queues
        if user.get("queues"):
            output.append(f"Queues:         {', '.join(user['queues'][:3])}")
            if len(user["queues"]) > 3:
                output.append(f"                ... and {len(user['queues']) - 3} more")

        output.append("")

    if not result.get("azureAD") and not result.get("genesys"):
        output.append("No results found in any system.")

    return "\n".join(output)


def hack_the_planet():
    """Hack the planet!"""
    output = """
[INITIATING HACK THE PLANET PROTOCOL]
=====================================

Accessing mainframe...
Bypassing firewall... [################] 100%
Cracking encryption... [################] 100%
Uploading virus... [################] 100%

ACCESS GRANTED

 _   _            _      _   _            ____  _                  _   
| | | | __ _  ___| | __ | |_| |__   ___  |  _ \\| | __ _ _ __   ___| |_ 
| |_| |/ _` |/ __| |/ / | __| '_ \\ / _ \\ | |_) | |/ _` | '_ \\ / _ \\ __|
|  _  | (_| | (__|   <  | |_| | | |  __/ |  __/| | (_| | | | |  __/ |_ 
|_| |_|\\__,_|\\___|_|\\_\\  \\__|_| |_|\\___| |_|   |_|\\__,_|_| |_|\\___|\\__|

MESS WITH THE BEST, DIE LIKE THE REST!

[System Message]: Just kidding! No actual hacking performed. 
Remember: Only hack systems you own or have permission to test!
"""

    return jsonify(
        {
            "success": True,
            "output": output,
            "type": "matrix",  # Special type for cool effect
        }
    )


def hack_the_gibson():
    """Access the Gibson!"""
    output = """
[ACCESSING GIBSON SUPERCOMPUTER]
================================

Dialing into Gibson...
Phone number: 555-0001
Modem handshake: CONNECT 2400

Login: plague
Password: ********

GIBSON SUPERCOMPUTER - ELLINGSON MINERAL COMPANY
-------------------------------------------------

Welcome to the Gibson. The most beautiful mainframe in the world.

Current users online: 5
- root
- plague
- joey
- cereal_killer
- acid_burn

Type 'ls' to list files...
Just kidding! This is just a movie reference.

"You're in the butter zone now, baby!"
"""

    return jsonify({"success": True, "output": output, "type": "matrix"})


def show_matrix():
    """Enter the Matrix."""
    output = """
Wake up, Neo...
The Matrix has you...
Follow the white rabbit.

Knock, knock, Neo.

    ╔═══════════════════════════════════════╗
    ║  01001101 01100001 01110100 01110010  ║
    ║  01101001 01111000 00100000 01101000  ║
    ║  01100001 01110011 00100000 01111001  ║
    ║  01101111 01110101 00101110 00101110  ║
    ╔═══════════════════════════════════════╗

There is no spoon.

Would you like to know more? Take the red pill...
Or return to blissful ignorance with the blue pill.
"""

    return jsonify({"success": True, "output": output, "type": "matrix"})


def ping_target(target):
    """Ping a target (fake, of course)."""
    import random

    # Generate random response times
    times = [random.randint(10, 100) for _ in range(4)]

    output = f"PING {target} ({target}) 56(84) bytes of data.\n"

    for i, ms in enumerate(times):
        output += f"64 bytes from {target}: icmp_seq={i + 1} ttl=64 time={ms} ms\n"

    output += f"\n--- {target} ping statistics ---\n"
    output += "4 packets transmitted, 4 received, 0% packet loss\n"
    output += f"rtt min/avg/max/mdev = {min(times)}/{sum(times) / 4:.1f}/{max(times)}/0.0 ms\n"

    return jsonify({"success": True, "output": output, "type": "info"})


def make_sandwich():
    """Handle the classic sudo make me sandwich."""
    output = (
        """
Okay.

    .-"""
        """-.
   /          \\
  |    ____    |
  |   |____|   |
  |            |
  |  ~~~~~~~~  |
  |  ========  |
  |    ____    |
  |   |____|   |
   \\          /
    '-......-'

Here's your sandwich. With great power comes great hunger.
"""
    )

    return jsonify({"success": True, "output": output, "type": "info"})


def show_uptime():
    """Show system uptime."""
    import random

    days = random.randint(1, 365)
    hours = random.randint(0, 23)
    minutes = random.randint(0, 59)

    output = f"""System uptime: {days} days, {hours}:{minutes:02d}
Load average: 0.{random.randint(10, 99)}, 0.{random.randint(10, 99)}, 0.{random.randint(10, 99)}
Active hacks: {random.randint(0, 1337)}
Coffee consumed: {random.randint(100, 9999)} cups
Bugs squashed: {random.randint(42, 420)}
Features shipped: {random.randint(1, 42)}
"""

    return jsonify({"success": True, "output": output, "type": "info"})


def show_fortune():
    """Show a hacker fortune."""
    import random

    fortunes = [
        "Your code will compile on the first try today.\n(Just kidding, check your semicolons)",
        "A SQL injection awaits you in your future.\nBetter sanitize those inputs!",
        "The bug you're looking for is on line 42.\nIt's always line 42.",
        "Your future holds many merge conflicts.\nMay the git be with you.",
        "Today you will discover that the problem was DNS.\nIt's always DNS.",
        "Your rubber duck has the answer you seek.\nJust explain it one more time.",
        "The stack overflow answer you need has been deleted.\nSuch is the way of the coder.",
        "Your next coffee will grant +10 to debugging.\nBrew wisely.",
        "A wild race condition appears!\nIt will only manifest in production.",
        "The intern's code review awaits.\nBrace yourself.",
        "Your future holds a date with legacy code.\nNo documentation included.",
        "Today's lucky numbers: 127.0.0.1\nThere's no place like home.",
        "You will soon discover a 5-year-old TODO comment.\nIt will remain unfixed.",
        "The force is strong with this commit.\nUntil the CI pipeline fails.",
        "Your code is like a bonsai tree.\nSmall, elegant, and impossible to maintain.",
    ]

    fortune = random.choice(fortunes)

    output = f"""
╔══════════════════════════════════════╗
║         HACKER'S FORTUNE             ║
╠══════════════════════════════════════╣
║                                      ║
  {fortune}
║                                      ║
╚══════════════════════════════════════╝
"""

    return jsonify({"success": True, "output": output, "type": "info"})
